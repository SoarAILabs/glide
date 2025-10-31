// Minimal queries for ingesting Git graph data and retrieving semantic diffs.
// Commit messages are generated in the app using retrieved diff summaries.

// Ingestion helpers

// createRepository: creates the root repository node; needed to scope all data.
QUERY createRepository(repo_id: String, name: String) =>
    repo <- AddN<Repository>({
        repo_id: repo_id,
        name: name
    })
    RETURN repo

// createBranch: creates a branch and links it to its repo
QUERY createBranch(repo_id: String, branch_id: String, name: String) =>
    repo <- N<Repository>({repo_id: repo_id})
    branch <- AddN<Branch>({
        branch_id: branch_id,
        name: name
    })
    AddE<HAS_BRANCH>()::From(repo)::To(branch)
    RETURN branch

// createCommit: creates a commit on a branch
QUERY createCommit(
    branch_id: String,
    commit_id: String,
    short_id: String,
    author: String,
    committed_at: Date,
    is_merge: Boolean
) =>
    branch <- N<Branch>({branch_id: branch_id})
    commit <- AddN<Commit>({
        commit_id: commit_id,
        short_id: short_id,
        author: author,
        committed_at: committed_at,
        is_merge: is_merge
    })
    AddE<HAS_COMMIT>()::From(branch)::To(commit)
    RETURN commit


// LinkParentCommit: records DAG parentage
QUERY linkParentCommit(child_commit_id: String, parent_commit_id: String) =>
    child <- N<Commit>({commit_id: child_commit_id})
    parent <- N<Commit>({commit_id: parent_commit_id})
    AddE<PARENT>()::From(child)::To(parent)
    RETURN "OK"


// createFile: creates a file node; enables path-scoped queries and file-level analytics.
QUERY createFile(file_id: String, path: String, language: String) =>
    file <- AddN<File>({
        file_id: file_id,
        path: path,
        language: language
    })
    RETURN file


// createDiff: attaches a diff with a precomputed Voyage vector
QUERY createDiff(
    commit_id: String,
    file_id: String,
    diff_id: String,
    kind: String,
    additions: I64,
    deletions: I64,
    summary: String,
    vec: [F64]
) =>
    commit <- N<Commit>({commit_id: commit_id})
    file <- N<File>({file_id: file_id})
    diff <- AddN<Diff>({
        diff_id: diff_id,
        kind: kind,
        additions: additions,
        deletions: deletions,
        summary: summary
    })
    embedding <- AddV<DiffEmbedding>(vec)
    AddE<HAS_DIFF>()::From(commit)::To(diff)
    AddE<AFFECTS_FILE>()::From(diff)::To(file)
    AddE<HAS_EMBEDDING>()::From(diff)::To(embedding)
    RETURN diff




// Search & retrieval

// getSimilarDiffsByVector: ANN over diffs using vectors
QUERY getSimilarDiffsByVector(vec: [F64], k: I64) =>
    embeddings <- SearchV<DiffEmbedding>(vec, k)
    results <- embeddings::In<HAS_EMBEDDING>
    RETURN results::{
        diff_id: diff_id,
        kind: kind,
        additions: additions,
        deletions: deletions,
        summary: summary,
        commit_id: _::In<HAS_DIFF>::{commit_id},
        commit_message: _::In<HAS_DIFF>::{message},
        file_path: _::Out<AFFECTS_FILE>::{path}
    }


// getDiffIdsForRepo: collects diff IDs under a repo
QUERY getDiffIdsForRepo(repo_id: String) =>
    diffs <- N<Repository>({repo_id: repo_id})::Out<HAS_BRANCH>::Out<HAS_COMMIT>::Out<HAS_DIFF>
    RETURN diffs::{ diff_id: diff_id }


// getDiffIdsForBranch: collects diff IDs under a branch
QUERY getDiffIdsForBranch(branch_id: String) =>
    diffs <- N<Branch>({branch_id: branch_id})::Out<HAS_COMMIT>::Out<HAS_DIFF>
    RETURN diffs::{ diff_id: diff_id }

// GetCommitDiffSummaries: returns per-diff summaries and paths for a commit
QUERY getCommitDiffSummaries(commit_id: String) =>
    diffs <- N<Commit>({commit_id: commit_id})::Out<HAS_DIFF>
    RETURN diffs::{
        diff_id: diff_id,
        kind: kind,
        additions: additions,
        deletions: deletions,
        summary: summary,
        file_path: _::Out<AFFECTS_FILE>::{path}
    }
