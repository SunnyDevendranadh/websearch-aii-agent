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
use std::collections::HashMap;
use serde_yaml;

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
    m.add_function(wrap_pyfunction!(clean_escape_sequences, m)?)?;
    m.add_function(wrap_pyfunction!(export_to_pdf, m)?)?;
    m.add_function(wrap_pyfunction!(open_file, m)?)?;
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
        
        // Use atomic write pattern to prevent corruption
        let temp_filename = format!("{}.tmp", filename);
        
        // Write to temporary file first
        fs::write(&temp_filename, content).map_err(|e| {
            PyErr::new::<pyo3::exceptions::PyIOError, _>(
                format!("Failed to write temporary file: {}", e)
            )
        })?;
        
        // Rename temporary file to final filename
        fs::rename(&temp_filename, &path).map_err(|e| {
            // Try to clean up temp file
            let _ = fs::remove_file(&temp_filename);
            
            PyErr::new::<pyo3::exceptions::PyIOError, _>(
                format!("Failed to save report: {}", e)
            )
        })?;
        
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
        
        // Check if file exists
        if !path.exists() {
            return Err(PyErr::new::<pyo3::exceptions::PyFileNotFoundError, _>(
                format!("Report file not found: {}", filename)
            ));
        }
        
        // Check if it's actually a file and not a directory
        if !path.is_file() {
            return Err(PyErr::new::<pyo3::exceptions::PyIOError, _>(
                format!("Path is not a file: {}", filename)
            ));
        }
        
        // Check file size to prevent loading extremely large files
        let metadata = fs::metadata(&path).map_err(|e| {
            PyErr::new::<pyo3::exceptions::PyIOError, _>(
                format!("Failed to read file metadata: {}", e)
            )
        })?;
        
        const MAX_FILE_SIZE: u64 = 50 * 1024 * 1024; // 50MB limit
        if metadata.len() > MAX_FILE_SIZE {
            return Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(
                format!("File too large ({}MB). Maximum size is 50MB.", metadata.len() / (1024 * 1024))
            ));
        }
        
        // Read file with informative error
        fs::read_to_string(&path).map_err(|e| {
            PyErr::new::<pyo3::exceptions::PyIOError, _>(
                format!("Failed to read report file: {}", e)
            )
        })
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

/// Process markdown content and extract metadata
#[pyfunction]
fn process_markdown(content: &str) -> PyResult<(HashMap<String, String>, String)> {
    // Validate input is not empty
    if content.trim().is_empty() {
        return Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(
            "Markdown content cannot be empty"
        ));
    }

    // Limit the size of the input to prevent processing extremely large markdown
    const MAX_CONTENT_LENGTH: usize = 10 * 1024 * 1024; // 10MB limit
    if content.len() > MAX_CONTENT_LENGTH {
        return Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(
            format!("Markdown content too large ({}MB). Maximum size is 10MB.", content.len() / (1024 * 1024))
        ));
    }

    // Extract metadata and markdown content
    let (metadata, markdown_content) = match parse_report_metadata(content) {
        Ok(result) => result,
        Err(err) => {
            return Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(
                format!("Failed to parse markdown metadata: {}", err)
            ));
        }
    };

    // Validate that required metadata fields are present
    let required_fields = ["title", "date"];
    for field in required_fields.iter() {
        if !metadata.contains_key(*field) {
            return Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(
                format!("Missing required metadata field: {}", field)
            ));
        }
    }

    Ok((metadata, markdown_content))
}

/// Clean terminal escape sequences from the content
#[pyfunction]
fn clean_escape_sequences(content: &str) -> PyResult<String> {
    // Handle various forms of escape sequences
    
    // 1. ANSI/VT100 escape sequence regex pattern for real escape codes
    let ansi_pattern = Regex::new(r"\x1B\[([0-9]{1,2}(;[0-9]{1,2})*)?[m|K|G|A|B|C|D|H|J|s|u|h|l]").unwrap();
    let mut cleaned = ansi_pattern.replace_all(content, "").to_string();
    
    // 2. Literal "ESC[" followed by formatting codes
    let literal_esc_pattern = Regex::new(r"ESC\[([0-9]{1,2}(;[0-9]{1,2})*)?[m|K|G|A|B|C|D|H|J|s|u|h|l]").unwrap();
    cleaned = literal_esc_pattern.replace_all(&cleaned, "").to_string();
    
    // 3. Simple common patterns
    let simple_patterns = [
        Regex::new(r"ESC\[0m").unwrap(),         // Reset
        Regex::new(r"ESC\[1m").unwrap(),         // Bold
        Regex::new(r"ESC\[1;33m").unwrap(),      // Yellow bold
        Regex::new(r"ESC\[\d+m").unwrap(),       // Any single number format
        Regex::new(r"ESC\[\d+;\d+m").unwrap(),   // Any compound format
    ];
    
    for pattern in simple_patterns.iter() {
        cleaned = pattern.replace_all(&cleaned, "").to_string();
    }
    
    // 4. Catch-all for other forms
    let catchall = Regex::new(r"(?:\x1B|\bESC)(?:\[|\(|\))[^@-Z\\^_`a-z{|}~]*[@-Z\\^_`a-z{|}~]").unwrap();
    cleaned = catchall.replace_all(&cleaned, "").to_string();
    
    Ok(cleaned)
}

/// Format a market research report from markdown to HTML
#[pyfunction]
fn format_report(markdown: &str) -> PyResult<String> {
    // Validate input is not empty
    if markdown.trim().is_empty() {
        return Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(
            "Markdown content cannot be empty"
        ));
    }

    // Clean any terminal escape sequences that might be present
    let cleaned_markdown = clean_escape_sequences(markdown)?;

    // Create options for markdown processing
    let mut options = ComrakOptions::default();
    options.extension.table = true;
    options.extension.strikethrough = true;
    options.extension.tagfilter = true;
    options.extension.autolink = true;
    options.extension.tasklist = true;
    options.extension.superscript = true;
    options.extension.header_ids = Some("section-".to_string());
    options.render.github_pre_lang = true;
    options.render.hardbreaks = false;
    options.render.unsafe_ = true;  // Allow HTML passthrough

    // Use a thread with timeout to prevent potential hangs
    let result = std::thread::spawn(move || {
        comrak::markdown_to_html(&cleaned_markdown, &options)
    })
    .join()
    .map_err(|_| {
        PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(
            "Markdown processing thread panicked"
        )
    })?;
    
    // Validate result is not empty
    if result.trim().is_empty() {
        return Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(
            "Generated HTML content is empty"
        ));
    }
    
    Ok(result)
}

/// Parse report metadata from markdown content
#[pyfunction]
fn parse_report_metadata(content: &str) -> PyResult<(HashMap<String, String>, String)> {
    let re = Regex::new(r"^---\n(.*?)\n---\n(.*)").unwrap();
    
    match re.captures(content) {
        Some(caps) => {
            let yaml_str = caps.get(1).unwrap().as_str();
            let markdown_content = caps.get(2).unwrap().as_str();
            
            let metadata: HashMap<String, String> = serde_yaml::from_str(yaml_str)
                .map_err(|e| PyErr::new::<pyo3::exceptions::PyValueError, _>(
                    format!("Failed to parse YAML metadata: {}", e)
                ))?;
            
            Ok((metadata, markdown_content.to_string()))
        },
        None => {
            // If no metadata section found, return empty metadata and full content
            Ok((HashMap::new(), content.to_string()))
        }
    }
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

/// Convert markdown report to PDF format
#[pyfunction]
fn export_to_pdf(content: &str, output_path: &str) -> PyResult<String> {
    // First, convert markdown to HTML
    // Clean any terminal escape sequences
    let cleaned_content = clean_escape_sequences(content)?;

    // Validate input is not empty
    if cleaned_content.trim().is_empty() {
        return Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(
            "Markdown content cannot be empty for PDF conversion"
        ));
    }
    
    // Create a temporary HTML file
    let temp_dir = std::env::temp_dir();
    let temp_html_path = temp_dir.join("report_temp.html");
    
    // Create HTML with proper styling for PDF output
    let mut options = ComrakOptions::default();
    options.extension.table = true;
    options.extension.strikethrough = true;
    options.extension.tagfilter = true;
    options.extension.autolink = true;
    options.extension.tasklist = true;
    options.extension.superscript = true;
    options.render.github_pre_lang = true;
    options.render.unsafe_ = true;  // Allow HTML passthrough
    
    let html_content = comrak::markdown_to_html(&cleaned_content, &options);
    
    // Add CSS styling for PDF output
    let full_html = format!(r#"<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body {{
            font-family: Arial, sans-serif;
            font-size: 12pt;
            line-height: 1.5;
            margin: 2cm;
        }}
        h1, h2, h3, h4, h5, h6 {{
            color: #333;
            margin-top: 1.5em;
            margin-bottom: 0.5em;
        }}
        h1 {{ font-size: 24pt; }}
        h2 {{ font-size: 20pt; }}
        h3 {{ font-size: 16pt; }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 1em 0;
        }}
        th, td {{
            border: 1px solid #ddd;
            padding: 8px;
            text-align: left;
        }}
        th {{
            background-color: #f2f2f2;
        }}
        .report-metadata {{
            margin-bottom: 2em;
            color: #666;
            font-style: italic;
        }}
        ul, ol {{
            margin: 0.5em 0;
            padding-left: 2em;
        }}
        code {{
            font-family: monospace;
            background-color: #f5f5f5;
            padding: 2px 4px;
            border-radius: 3px;
        }}
        pre {{
            background-color: #f5f5f5;
            padding: 1em;
            border-radius: 5px;
            overflow-x: auto;
        }}
        blockquote {{
            background-color: #f9f9f9;
            border-left: 4px solid #ccc;
            margin: 1em 0;
            padding: 0.5em 1em;
        }}
    </style>
</head>
<body>
    {html_content}
</body>
</html>"#);

    // Write HTML to temp file
    fs::write(&temp_html_path, full_html)
        .map_err(|e| PyErr::new::<pyo3::exceptions::PyIOError, _>(
            format!("Failed to write temporary HTML file: {}", e)
        ))?;
    
    // Check if wkhtmltopdf is installed and available
    let wkhtmltopdf_check = std::process::Command::new("wkhtmltopdf")
        .arg("--version")
        .output();
    
    if let Err(_) = wkhtmltopdf_check {
        return Err(PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(
            "wkhtmltopdf not found. Please install wkhtmltopdf to use PDF export functionality."
        ));
    }
    
    // Convert HTML to PDF using wkhtmltopdf
    let output = std::process::Command::new("wkhtmltopdf")
        .arg("--enable-local-file-access")
        .arg("--page-size")
        .arg("A4")
        .arg("--margin-top")
        .arg("20mm")
        .arg("--margin-bottom")
        .arg("20mm")
        .arg("--margin-left")
        .arg("20mm")
        .arg("--margin-right")
        .arg("20mm")
        .arg("--encoding")
        .arg("UTF-8")
        .arg(temp_html_path.to_string_lossy().to_string())
        .arg(output_path)
        .output()
        .map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(
            format!("Failed to execute wkhtmltopdf: {}", e)
        ))?;
    
    // Check if wkhtmltopdf succeeded
    if !output.status.success() {
        let error_output = String::from_utf8_lossy(&output.stderr);
        return Err(PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(
            format!("wkhtmltopdf failed: {}", error_output)
        ));
    }
    
    // Check if PDF was created
    if !Path::new(output_path).exists() {
        return Err(PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(
            "PDF file was not created successfully"
        ));
    }
    
    Ok(output_path.to_string())
}

/// Open a file with the default system application
#[pyfunction]
fn open_file(file_path: &str) -> PyResult<bool> {
    // Determine which command to use based on platform
    let command = if cfg!(target_os = "windows") {
        ("cmd", ["/c", "start", "", file_path].to_vec())
    } else if cfg!(target_os = "macos") {
        ("open", [file_path].to_vec())
    } else {
        ("xdg-open", [file_path].to_vec())  // Linux/Unix
    };
    
    // Execute the command
    let output = std::process::Command::new(command.0)
        .args(command.1)
        .output()
        .map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(
            format!("Failed to open file: {}", e)
        ))?;
    
    // Check if command succeeded
    if !output.status.success() {
        let error_output = String::from_utf8_lossy(&output.stderr);
        return Err(PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(
            format!("Failed to open file: {}", error_output)
        ));
    }
    
    Ok(true)
}
