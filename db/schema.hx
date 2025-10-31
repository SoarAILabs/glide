// Nodes
N::Repository {
  repo_id: String PRIMARY KEY,
  name: String UNIQUE,
  created_at: Date DEFAULT NOW
}

N::Branch {
  branch_id: String PRIMARY KEY,
  name: String,
  created_at: Date DEFAULT NOW
}

N::Commit {
  commit_id: String PRIMARY KEY,    // full hash
  short_id: String,                 // optional short hash
  author: String,
  message: String,
  committed_at: Date,
  is_merge: Bool DEFAULT false
}

N::File {
  file_id: String PRIMARY KEY,
  path: String,                     // repo-relative path
  language: String                  // optional, for better grouping
}

N::Diff {
  diff_id: String PRIMARY KEY,
  kind: String,                     // add|mod|del|rename|move|meta
  additions: Int,
  deletions: Int,
  summary: String,                  // LLM-ready textual summary
  embedding: Vector<1536> INDEX HNSW(metric: COSINE)
}

// Edges
E::HAS_BRANCH(Repository -> Branch)
E::HAS_COMMIT(Branch -> Commit)
E::PARENT(Commit -> Commit)
E::HAS_DIFF(Commit -> Diff)
E::AFFECTS_FILE(Diff -> File)