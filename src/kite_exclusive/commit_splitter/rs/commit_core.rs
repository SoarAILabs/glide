use pyo3::prelude::*;


#[pyfunction]
pub fn commit_splitter() -> PyResult<String> {
    let gemini_result = gemini_service()?;
    let helix_result = helix_service()?;
    let voyage_result = voyage_service()?;
    Ok(format!("Commit splitter running in rust, successfully. yea im shocked too. it has these functions in it: {},{},{}", gemini_result, helix_result, voyage_result))
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
pub fn voyage_service() -> PyResult<String> {
    println!("voyage service running in rust, successfully. yea im shocked too");
    Ok("Voyage service running in rust, successfully. yea im shocked too".to_string())
}

