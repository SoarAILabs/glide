use pyo3::prelude::*;

mod kite_exclusive {
    pub mod commit_splitter {
        pub mod rs {
            pub mod commit_core;
        }
    }
}
use kite_exclusive::commit_splitter::rs::commit_core::{commit_splitter, gemini_service, helix_service, voyage_service};


#[pymodule]
fn glide(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(commit_splitter, m)?)?;
    m.add_function(wrap_pyfunction!(gemini_service, m)?)?;
    m.add_function(wrap_pyfunction!(helix_service, m)?)?;
    m.add_function(wrap_pyfunction!(voyage_service, m)?)?;
    Ok(())
}
