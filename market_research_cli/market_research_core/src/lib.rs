use pyo3::prelude::*;
use pyo3::types::{PyDict, PyList};
use std::fs;
use std::path::Path;
use std::sync::{Arc, Mutex};
use std::time::Instant;
use serde::{Deserialize, Serialize};
use anyhow::{Result, anyhow};
use comrak::{markdown_to_html, ComrakOptions};
use chrono::prelude::*;
use regex::Regex;

/// A Rust module for accelerating market research report generation.
/// This module provides high-performance alternatives to slow Python operations.
#[pymodule]
fn market_research_core(_py: Python, m: &PyModule) -> PyResult<()> {
    m.add_class::<ProgressTracker>()?;
    m.add_class::<ReportManager>()?;
    m.add_function(wrap_pyfunction!(process_markdown, m)?)?;
    m.add_function(wrap_pyfunction!(format_report, m)?)?;
    m.add_function(wrap_pyfunction!(parse_report_metadata, m)?)?;
    m.add_function(wrap_pyfunction!(py_list_reports, m)?)?;
    Ok(())
}

/// Thread-safe progress tracker for report generation
#[pyclass]
struct ProgressTracker {
    progress: Arc<Mutex<ProgressData>>,
    start_time: Arc<Mutex<Instant>>,
}

struct ProgressData {
    percentage: f32,
    stage: String,
    agent: String,
    activity: String,
}

#[pymethods]
impl ProgressTracker {
    #[new]
    fn new() -> Self {
        ProgressTracker {
            progress: Arc::new(Mutex::new(ProgressData {
                percentage: 0.0,
                stage: "Initializing".to_string(),
                agent: "System".to_string(),
                activity: "Starting up".to_string(),
            })),
            start_time: Arc::new(Mutex::new(Instant::now())),
        }
    }

    /// Update the progress of report generation
    fn update(&self, percentage: f32, stage: &str, agent: &str, activity: &str) -> PyResult<()> {
        let mut data = self.progress.lock().unwrap();
        data.percentage = percentage;
        data.stage = stage.to_string();
        data.agent = agent.to_string();
        data.activity = activity.to_string();
        Ok(())
    }

    /// Get the current progress data
    fn get_progress(&self, py: Python) -> PyResult<PyObject> {
        let data = self.progress.lock().unwrap();
        let dict = PyDict::new(py);
        dict.set_item("percentage", data.percentage)?;
        dict.set_item("stage", &data.stage)?;
        dict.set_item("agent", &data.agent)?;
        dict.set_item("activity", &data.activity)?;
        dict.set_item("elapsed_seconds", self.get_elapsed_seconds())?;
        Ok(dict.into())
    }

    /// Get elapsed time in seconds
    fn get_elapsed_seconds(&self) -> f32 {
        let start = self.start_time.lock().unwrap();
        start.elapsed().as_secs_f32()
    }

    /// Reset the progress tracker
    fn reset(&self) -> PyResult<()> {
        let mut data = self.progress.lock().unwrap();
        data.percentage = 0.0;
        data.stage = "Initializing".to_string();
        data.agent = "System".to_string();
        data.activity = "Starting up".to_string();
        
        let mut start = self.start_time.lock().unwrap();
        *start = Instant::now();
        Ok(())
    }
}

/// Manager for report files
#[pyclass]
struct ReportManager {
    reports_dir: String,
}

#[derive(Serialize, Deserialize)]
struct ReportMetadata {
    title: String,
    date: String,
    id: String,
}

#[pymethods]
impl ReportManager {
    #[new]
    fn new(reports_dir: &str) -> Self {
        ReportManager {
            reports_dir: reports_dir.to_string(),
        }
    }

    /// Save a report to disk
    fn save_report(&self, filename: &str, content: &str) -> PyResult<String> {
        let path = Path::new(&self.reports_dir).join(filename);
        
        // Create directory if it doesn't exist
        if let Some(parent) = path.parent() {
            if !parent.exists() {
                fs::create_dir_all(parent)
                    .map_err(|e| PyErr::new::<pyo3::exceptions::PyIOError, _>(format!("Failed to create directory: {}", e)))?;
            }
        }
        
        // Write file
        fs::write(&path, content)
            .map_err(|e| PyErr::new::<pyo3::exceptions::PyIOError, _>(format!("Failed to write file: {}", e)))?;
        
        Ok(path.to_string_lossy().to_string())
    }

    /// Get a list of all reports
    fn get_all_reports(&self, py: Python) -> PyResult<PyObject> {
        let reports = list_reports(&self.reports_dir)
            .map_err(|e| PyErr::new::<pyo3::exceptions::PyIOError, _>(format!("Failed to list reports: {}", e)))?;
        
        let result = PyList::new(py, &reports);
        Ok(result.into())
    }

    /// Read a report from disk
    fn read_report(&self, filename: &str) -> PyResult<String> {
        let path = Path::new(&self.reports_dir).join(filename);
        let result = fs::read_to_string(&path)
            .map_err(|e| PyErr::new::<pyo3::exceptions::PyIOError, _>(format!("Failed to read file: {}", e)))?;
        
        Ok(result)
    }

    /// Delete a report
    fn delete_report(&self, filename: &str) -> PyResult<bool> {
        let path = Path::new(&self.reports_dir).join(filename);
        
        if path.exists() {
            fs::remove_file(&path)
                .map_err(|e| PyErr::new::<pyo3::exceptions::PyIOError, _>(format!("Failed to delete file: {}", e)))?;
            Ok(true)
        } else {
            Ok(false)
        }
    }
}

/// Process markdown content
#[pyfunction]
fn process_markdown(markdown: &str) -> PyResult<String> {
    let mut options = ComrakOptions::default();
    options.extension.table = true;
    options.extension.strikethrough = true;
    options.extension.tagfilter = true;
    options.extension.autolink = true;
    
    Ok(markdown_to_html(markdown, &options))
}

/// Format a report with proper styling
#[pyfunction]
fn format_report(content: &str, title: &str) -> PyResult<String> {
    let current_date = Local::now().format("%B %d, %Y").to_string();
    let report_id = Local::now().format("MR-%Y%m%d-%H%M%S").to_string();
    
    let formatted = format!(
        "# {} Market Analysis\n\n\
        <div class=\"report-metadata\">\n\
        <p class=\"report-date\">Generated on: {}</p>\n\
        <p class=\"report-id\">Report ID: {}</p>\n\
        <p class=\"confidentiality\">CONFIDENTIAL DOCUMENT</p>\n\
        </div>\n\n\
        ---\n\n\
        {}", 
        title, current_date, report_id, content
    );
    
    Ok(formatted)
}

/// Parse metadata from a report
#[pyfunction]
fn parse_report_metadata(py: Python, content: &str) -> PyResult<PyObject> {
    let title_re = Regex::new(r"#\s*(.*?)(?:\n|$)").unwrap();
    let date_re = Regex::new(r"Generated on:\s*(.*?)(?:\n|<)").unwrap();
    let id_re = Regex::new(r"Report ID:\s*(.*?)(?:\n|<)").unwrap();
    
    let title = title_re.captures(content)
        .and_then(|cap| cap.get(1))
        .map(|m| m.as_str().trim().to_string())
        .unwrap_or_else(|| "Unknown Title".to_string());
    
    let date = date_re.captures(content)
        .and_then(|cap| cap.get(1))
        .map(|m| m.as_str().trim().to_string())
        .unwrap_or_else(|| "Unknown Date".to_string());
    
    let id = id_re.captures(content)
        .and_then(|cap| cap.get(1))
        .map(|m| m.as_str().trim().to_string())
        .unwrap_or_else(|| "Unknown ID".to_string());
    
    let dict = PyDict::new(py);
    dict.set_item("title", title)?;
    dict.set_item("date", date)?;
    dict.set_item("id", id)?;
    
    Ok(dict.into())
}

/// Python-exposed function for listing reports
#[pyfunction]
fn py_list_reports(dir_path: &str) -> PyResult<Vec<String>> {
    list_reports(dir_path)
        .map_err(|e| PyErr::new::<pyo3::exceptions::PyIOError, _>(format!("Failed to list reports: {}", e)))
}

/// List all report files (internal implementation)
fn list_reports(dir_path: &str) -> Result<Vec<String>> {
    let path = Path::new(dir_path);
    
    if !path.exists() {
        return Err(anyhow!("Reports directory does not exist"));
    }
    
    let entries = fs::read_dir(path)?
        .filter_map(|entry| {
            let entry = entry.ok()?;
            let path = entry.path();
            
            if path.is_file() && path.extension()?.to_str()? == "md" {
                Some(path.file_name()?.to_str()?.to_string())
            } else {
                None
            }
        })
        .collect();
    
    Ok(entries)
}
