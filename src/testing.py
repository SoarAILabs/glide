from glide import get_git_root, get_staged, get_unstaged, get_untracked

def test_git_rust():
    print("Git root: ", get_git_root())
    print("Staged: ", get_staged())
    print("Unstaged: ", get_unstaged())
    print("Untracked: ", get_untracked())

if __name__ == "__main__":
    test_git_rust()