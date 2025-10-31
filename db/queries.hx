// Minimal queries for ingesting Git graph data and retrieving semantic diffs.
// Commit messages are generated in the app using retrieved diff summaries.

// Ingestion helpers

// EnsureRepository: creates the root repository node; needed to scope all data.
QUERY EnsureRepository(repo_id: String, name: String) =>
    repo <- AddN<Repository>({
        repo_id: repo_id,
        name: name
    })
    RETURN repo

// EnsureBranch: creates a branch and links it to its repo; required for per-branch traversals.
QUERY EnsureBranch(repo_id: String, branch_id: String, name: String) =>
    repo <- N<Repository>(repo_id)
    branch <- AddN<Branch>({
        branch_id: branch_id,
        name: name
    })
    AddE<HAS_BRANCH>::From(repo)::To(branch_id)
    RETURN branch

// EnsureCommit: creates a commit on a branch; base unit for linking diffs and DAG parents.
QUERY EnsureCommit(
    branch_id: String,
    commit_id: String,
    short_id: String,
    author: String,
    committed_at: Date,
    is_merge: Bool
) =>
    branch <- N<Branch>(branch_id)
    commit <- AddN<Commit>({
        commit_id: commit_id,
        short_id: short_id,
        author: author,
        committed_at: committed_at,
        is_merge: is_merge
    })
    AddE<HAS_COMMIT>::From(branch)::To(commit_id)
    RETURN commit

// LinkParentCommit: records DAG parentage; required to reconstruct history and merges.
QUERY LinkParentCommit(child_commit_id: String, parent_commit_id: String) =>
    child <- N<Commit>(child_commit_id)
    parent <- N<Commit>(parent_commit_id)
    AddE<PARENT>::From(child)::To(parent_commit_id)
    RETURN "OK"

// EnsureFile: creates a file node; enables path-scoped queries and file-level analytics.
QUERY EnsureFile(file_id: String, path: String, language: String) =>
    file <- AddN<File>({
        file_id: file_id,
        path: path,
        language: language
    })
    RETURN file

// IngestDiff: attaches a diff with a precomputed Voyage vector; enables ANN over code changes.
QUERY IngestDiff(
    commit_id: String,
    file_id: String,
    diff_id: String,
    kind: String,
    additions: I64,
    deletions: I64,
    summary: String,
    vec: [F64]
) =>
    commit <- N<Commit>(commit_id)
    file <- N<File>(file_id)
    diff <- AddN<Diff>({
        diff_id: diff_id,
        kind: kind,
        additions: additions,
        deletions: deletions,
        summary: summary,
        embedding: vec
    })
    AddE<HAS_DIFF>::From(commit)::To(diff_id)
    AddE<AFFECTS_FILE>::From(diff)::To(file_id)
    RETURN diff

// Search & retrieval

// SearchSimilarDiffsByVector: ANN over diffs using Voyage vectors; core primitive for similarity.
QUERY SearchSimilarDiffsByVector(vec: [F64], k: I64) =>
    results <- SearchV<Diff>(vec, k)
    RETURN results::{
        diff_id: diff_id,
        kind: kind,
        additions: additions,
        deletions: deletions,
        summary: summary,
        commit_id: _::In<HAS_DIFF>::commit_id,
        commit_message: _::In<HAS_DIFF>::message,
        file_path: _::Out<AFFECTS_FILE>::path
    }

// GetDiffIdsForRepo: collects diff IDs under a repo; used to intersect with ANN results.
QUERY GetDiffIdsForRepo(repo_id: String) =>
    diffs <- N<Repository>(repo_id)::Out<HAS_BRANCH>::Out<HAS_COMMIT>::Out<HAS_DIFF>
    RETURN diffs::{ diff_id: diff_id }

// GetDiffIdsForBranch: collects diff IDs under a branch; narrows similarity to a branch.
QUERY GetDiffIdsForBranch(branch_id: String) =>
    diffs <- N<Branch>(branch_id)::Out<HAS_COMMIT>::Out<HAS_DIFF>
    RETURN diffs::{ diff_id: diff_id }

// GetCommitDiffSummaries: returns per-diff summaries and paths for a commit; input to LLM summarizer.
QUERY GetCommitDiffSummaries(commit_id: String) =>
    diffs <- N<Commit>(commit_id)::Out<HAS_DIFF>
    RETURN diffs::{
        diff_id: diff_id,
        kind: kind,
        additions: additions,
        deletions: deletions,
        summary: summary,
        file_path: _::Out<AFFECTS_FILE>::path
    }
