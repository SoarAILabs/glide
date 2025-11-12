use pyo3::prelude::*;

pub mod diff;

/// Python module definition — the name here is the Python import name
#[pymodule]
fn glide(_py: Python, m: &PyModule) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(diff::get_git_root, m)?)?;
    m.add_function(wrap_pyfunction!(diff::get_staged, m)?)?;
    m.add_function(wrap_pyfunction!(diff::get_unstaged, m)?)?;
    m.add_function(wrap_pyfunction!(diff::get_untracked, m)?)?;
    Ok(())
}