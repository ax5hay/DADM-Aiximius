//! ONNX Runtime inference for anomaly score. Input: [1, feature_dim] f32, Output: score.
//! Uses `ort` crate; if model file is missing, runs in no-op mode (returns 0.0).

use crate::features::FeatureVector;
use ndarray::Array2;
use std::path::Path;
use std::sync::OnceLock;

static ORT_ENV: OnceLock<ort::Environment> = OnceLock::new();

fn init_env() -> &'static ort::Environment {
    ORT_ENV.get_or_init(|| {
        ort::Environment::builder()
            .with_name("dadm-agent")
            .build()
            .expect("ORT environment")
    })
}

pub struct OnnxDetector {
    session: Option<ort::Session>,
    input_name: String,
    feature_dim: usize,
}

impl OnnxDetector {
    /// Load model from path. If path missing or invalid, detector runs in no-op mode (returns 0.0).
    pub fn load(path: &Path, feature_dim: usize) -> Result<Self, ort::Error> {
        let _env = init_env();
        let path = path.to_path_buf();
        if !path.exists() {
            tracing::warn!(path = %path.display(), "ONNX model not found; inference disabled");
            return Ok(Self {
                session: None,
                input_name: String::new(),
                feature_dim,
            });
        }

        let session = ort::Session::builder()?
            .commit_from_file(&path)?;

        let input_name = session
            .inputs
            .first()
            .map(|i| i.name.clone())
            .unwrap_or_else(|| "input".to_string());

        Ok(Self {
            session: Some(session),
            input_name,
            feature_dim,
        })
    }

    /// Run inference; returns anomaly score in [0, 1]. Returns 0.0 if no model loaded.
    pub fn predict(&self, features: &FeatureVector) -> f32 {
        let Some(ref session) = self.session else {
            return 0.0;
        };

        let dim = self.feature_dim.min(features.values.len());
        let arr = Array2::from_shape_vec((1, dim), features.values[..dim].to_vec()).unwrap();
        let input = match ort::Value::from_array(arr.into_dyn()) {
            Ok(v) => v,
            Err(_) => return 0.0,
        };

        let outputs = match session.run(ort::inputs![self.input_name.as_str() => input]?) {
            Ok(o) => o,
            Err(_) => return 0.0,
        };

        let out = match outputs.get(0) {
            Some(t) => t,
            None => return 0.0,
        };
        let view = match out.try_extract_raw_tensor::<f32>() {
            Ok(v) => v,
            Err(_) => return 0.0,
        };
        let score = view.as_slice().first().copied().unwrap_or(0.0);
        score.clamp(0.0, 1.0)
    }
}
