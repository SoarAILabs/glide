// Nodes
N::Repository {
  INDEX repo_id: String,
  INDEX name: String,
  created_at: Date DEFAULT NOW
}

N::Branch {
  INDEX branch_id: String,
  name: String,
  created_at: Date DEFAULT NOW
}

N::Commit {
  INDEX commit_id: String,
  short_id: String,
  author: String,
  message: String,
  committed_at: Date,
  is_merge: Boolean DEFAULT false
}

N::File {
  INDEX file_id: String,
  path: String,
  language: String
}

N::Diff {
  INDEX diff_id: String,
  kind: String,
  additions: I64,
  deletions: I64,
  summary: String
}

// Vector type for embeddings
V::DiffEmbedding {
  vector: [F64]
}

// Edges
E::HAS_BRANCH {
  From: Repository,
  To: Branch,
  Properties: {}
}

E::HAS_COMMIT {
  From: Branch,
  To: Commit,
  Properties: {}
}

E::PARENT {
  From: Commit,
  To: Commit,
  Properties: {}
}

E::HAS_DIFF {
  From: Commit,
  To: Diff,
  Properties: {}
}

E::AFFECTS_FILE {
  From: Diff,
  To: File,
  Properties: {}
}

E::HAS_EMBEDDING {
  From: Diff,
  To: DiffEmbedding,
  Properties: {}
}
