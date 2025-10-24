use pyo3::prelude::*;

#[pymodule]
fn glide(_py: Python, m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(commit_splitter, m)?)?;
    m.add_function(wrap_pyfunction!(gemini_service, m)?)?;
    m.add_function(wrap_pyfunction!(helix_service, m)?)?;
    m.add_function(wrap_pyfunction!(embed_service, m)?)?;
    m.add_function(wrap_pyfunction!(git_diff_service, m)?)?;
    Ok(())
}

#[pyfunction]
pub fn commit_splitter() -> PyResult<String> {
    let gemini_result = gemini_service()?;
    let helix_result = helix_service()?;
    let voyage_result = embed_service()?;
    let git_diff_result = git_diff_service()?;
    Ok(format!("Commit splitter running in rust, successfully. yea im shocked too. it has these functions in it: {}, {},{},{}", gemini_result, helix_result, voyage_result, git_diff_result))
}

#[pyfunction]
pub fn git_diff_service() -> PyResult<String>{
    println!("git diff service running in rust, successfully. yea im shocked too");
    Ok("Git diff service running in rust, successfully. yea im shocked too".to_string())
}

#[pyfunction]
pub fn gemini_service() -> PyResult<String> {
    println!("gemini service running in rust, successfully. yea im shocked too");
    Ok("Gemini service running in rust, successfully. yea im shocked too".to_string())
}

#[pyfunction]
pub fn helix_service() -> PyResult<String> {
    println!("helix service running in rust, successfully. yea im shocked too");
    Ok("Helix service running in rust, successfully. yea im shocked too".to_string())
}

#[pyfunction]
pub fn embed_service() -> PyResult<String> {
    println!("voyage service running in rust, successfully. yea im shocked too");
    Ok("Voyage service running in rust, successfully. yea im shocked too".to_string())
}