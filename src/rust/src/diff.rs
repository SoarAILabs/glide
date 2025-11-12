use pyo3::prelude::*;
use std::process::Command;
use std::path::PathBuf;

#[pyfunction]
pub fn get_git_root() -> PyResult<String> {
    let output = Command::new("git")
        .arg("rev-parse")
        .arg("--show-toplevel")
        .output()
        .map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(
            format!("Failed to execute git command: {}", e)
        ))?;

    if !output.status.success() {
        let stderr = String::from_utf8_lossy(&output.stderr);
        return Err(PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(
            format!("Failed to find git root: {}", stderr)
        ));
    }

    let repo_root = String::from_utf8(output.stdout)
        .map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(
            format!("Failed to decode git root: {}", e)
        ))?
        .trim()
        .to_string();

    Ok(repo_root)
}

#[pyfunction]
pub fn get_staged() -> PyResult<String> {
    // Get the git repository root
    let repo_root = get_git_root()?;
    let repo_root_path = PathBuf::from(&repo_root);
    
    // Get staged changes
    let output = Command::new("git")
        .arg("diff")
        .arg("--cached")
        .current_dir(&repo_root_path)
        .output()
        .map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(
            format!("Failed to execute git command: {}", e)
        ))?;

    // Git diff returns exit code 1 when there are differences (which is normal)
    // Exit code 0 means no differences, exit code > 1 means error
    if output.status.code().unwrap_or(1) > 1 {
        let stderr = String::from_utf8_lossy(&output.stderr);
        return Err(PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(
            format!("Git command failed: {}", stderr)
        ));
    }

    let stdout = String::from_utf8(output.stdout)
        .map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(
            format!("Failed to decode output: {}", e)
        ))?;

    Ok(stdout)
}

#[pyfunction]
pub fn get_unstaged() -> PyResult<String> {
    // Get the git repository root
    let repo_root = get_git_root()?;
    let repo_root_path = PathBuf::from(&repo_root);
    
    // Get unstaged changes
    let output = Command::new("git")
        .arg("diff")
        .current_dir(&repo_root_path)
        .output()
        .map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(
            format!("Failed to execute git command: {}", e)
        ))?;

    // Git diff returns exit code 1 when there are differences (which is normal)
    // Exit code 0 means no differences, exit code > 1 means error
    if output.status.code().unwrap_or(1) > 1 {
        let stderr = String::from_utf8_lossy(&output.stderr);
        return Err(PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(
            format!("Git command failed: {}", stderr)
        ));
    }

    let stdout = String::from_utf8(output.stdout)
        .map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(
            format!("Failed to decode output: {}", e)
        ))?;

    Ok(stdout)
}

#[pyfunction]
pub fn get_untracked() -> PyResult<String> {
    // Get the git repository root
    let repo_root = get_git_root()?;
    let repo_root_path = PathBuf::from(&repo_root);
    
    // Get untracked files
    let output = Command::new("git")
        .arg("ls-files")
        .arg("--others")
        .arg("--exclude-standard")
        .current_dir(&repo_root_path)
        .output()
        .map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(
            format!("Failed to execute git command: {}", e)
        ))?;

    if !output.status.success() {
        let stderr = String::from_utf8_lossy(&output.stderr);
        return Err(PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(
            format!("Git command failed: {}", stderr)
        ));
    }

    let stdout = String::from_utf8(output.stdout)
        .map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(
            format!("Failed to decode output: {}", e)
        ))?;

    Ok(stdout)
}