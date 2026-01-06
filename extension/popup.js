/**
 * Resume Tailorer - Chrome Extension
 * Main popup script handling file uploads, API calls, and UI interactions
 */

const API_BASE = 'http://localhost:5000';

// DOM Elements
const elements = {
  // Status
  serverStatus: document.getElementById('serverStatus'),
  
  // Tabs
  tabs: document.querySelectorAll('.tab'),
  tabContents: document.querySelectorAll('.tab-content'),
  
  // Upload Tab
  dropzone: document.getElementById('dropzone'),
  fileInput: document.getElementById('fileInput'),
  filePreview: document.getElementById('filePreview'),
  fileName: document.getElementById('fileName'),
  fileType: document.getElementById('fileType'),
  previewContent: document.getElementById('previewContent'),
  removeFile: document.getElementById('removeFile'),
  
  // Tailor Tab
  resumeStatus: document.getElementById('resumeStatus'),
  jobDescription: document.getElementById('jobDescription'),
  tailorBtn: document.getElementById('tailorBtn'),
  loading: document.getElementById('loading'),
  result: document.getElementById('result'),
  resultContent: document.getElementById('resultContent'),
  copyResult: document.getElementById('copyResult'),
  downloadResult: document.getElementById('downloadResult'),
  downloadPdf: document.getElementById('downloadPdf'),
  
  // Context Tab
  ragContext: document.getElementById('ragContext'),
  loadContext: document.getElementById('loadContext'),
  saveContext: document.getElementById('saveContext'),
  
  // Toast
  toast: document.getElementById('toast')
};

// State
let currentTailoredContent = '';
let currentFileType = '';
let compiledPdfUrl = '';

// =====================
// Utility Functions
// =====================

function showToast(message, type = 'info') {
  const toast = elements.toast;
  toast.querySelector('.toast-message').textContent = message;
  toast.className = `toast ${type}`;
  toast.classList.add('show');
  
  setTimeout(() => {
    toast.classList.remove('show');
  }, 3000);
}

async function checkServerHealth() {
  try {
    const response = await fetch(`${API_BASE}/health`, { 
      method: 'GET',
      mode: 'cors'
    });
    
    if (response.ok) {
      elements.serverStatus.classList.add('connected');
      elements.serverStatus.classList.remove('disconnected');
      elements.serverStatus.querySelector('.status-text').textContent = 'Connected';
      return true;
    }
  } catch (error) {
    console.log('Server not available:', error);
  }
  
  elements.serverStatus.classList.add('disconnected');
  elements.serverStatus.classList.remove('connected');
  elements.serverStatus.querySelector('.status-text').textContent = 'Offline';
  return false;
}

async function updateResumeStatus() {
  try {
    const response = await fetch(`${API_BASE}/current-resume`);
    const data = await response.json();
    
    const statusBadge = elements.resumeStatus.querySelector('.status-badge');
    
    if (data.loaded) {
      statusBadge.className = 'status-badge loaded';
      const persistedLabel = data.persisted ? ' (saved)' : '';
      statusBadge.innerHTML = `
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/>
          <polyline points="22,4 12,14.01 9,11.01"/>
        </svg>
        ${data.filename}${persistedLabel}
      `;
    } else {
      statusBadge.className = 'status-badge pending';
      statusBadge.textContent = 'No resume loaded';
    }
  } catch (error) {
    console.error('Error checking resume status:', error);
  }
}

// =====================
// Tab Navigation
// =====================

function initTabs() {
  elements.tabs.forEach(tab => {
    tab.addEventListener('click', () => {
      const targetTab = tab.dataset.tab;
      
      // Update active states
      elements.tabs.forEach(t => t.classList.remove('active'));
      elements.tabContents.forEach(c => c.classList.remove('active'));
      
      tab.classList.add('active');
      document.getElementById(`${targetTab}Tab`).classList.add('active');
      
      // Refresh data when switching tabs
      if (targetTab === 'tailor') {
        updateResumeStatus();
      } else if (targetTab === 'context') {
        loadRagContext();
      }
    });
  });
}

// =====================
// File Upload
// =====================

function initDropzone() {
  const dropzone = elements.dropzone;
  const fileInput = elements.fileInput;
  
  // Click to browse
  dropzone.addEventListener('click', () => fileInput.click());
  
  // File selection
  fileInput.addEventListener('change', (e) => {
    if (e.target.files.length > 0) {
      handleFile(e.target.files[0]);
    }
  });
  
  // Drag and drop events
  ['dragenter', 'dragover'].forEach(event => {
    dropzone.addEventListener(event, (e) => {
      e.preventDefault();
      e.stopPropagation();
      dropzone.classList.add('dragover');
    });
  });
  
  ['dragleave', 'drop'].forEach(event => {
    dropzone.addEventListener(event, (e) => {
      e.preventDefault();
      e.stopPropagation();
      dropzone.classList.remove('dragover');
    });
  });
  
  dropzone.addEventListener('drop', (e) => {
    const files = e.dataTransfer.files;
    if (files.length > 0) {
      handleFile(files[0]);
    }
  });
  
  // Remove file button
  elements.removeFile.addEventListener('click', () => {
    elements.filePreview.classList.add('hidden');
    elements.fileInput.value = '';
    updateResumeStatus();
  });
}

async function handleFile(file) {
  const validTypes = ['text/x-tex', 'application/x-tex'];
  const validExtensions = ['.tex'];
  
  const hasValidExtension = validExtensions.some(ext => 
    file.name.toLowerCase().endsWith(ext)
  );
  
  if (!hasValidExtension && !validTypes.includes(file.type)) {
    showToast('Please upload a LaTeX (.tex) file', 'error');
    return;
  }
  
  // Create form data
  const formData = new FormData();
  formData.append('file', file);
  
  try {
    showToast('Uploading file...', 'info');
    
    const response = await fetch(`${API_BASE}/upload`, {
      method: 'POST',
      body: formData
    });
    
    const data = await response.json();
    
    if (data.error) {
      showToast(data.error, 'error');
      return;
    }
    
    // Update UI
    elements.fileName.textContent = data.filename;
    elements.fileType.textContent = getFileTypeLabel(data.file_type);
    elements.previewContent.textContent = data.preview;
    elements.filePreview.classList.remove('hidden');
    currentFileType = data.file_type;
    
    showToast('Resume uploaded successfully!', 'success');
    updateResumeStatus();
    
  } catch (error) {
    console.error('Upload error:', error);
    showToast('Failed to upload file. Is the server running?', 'error');
  }
}

function getFileTypeLabel(type) {
  const labels = {
    'pdf': 'PDF Document',
    'tex': 'LaTeX File',
    'txt': 'Text File'
  };
  return labels[type] || type.toUpperCase();
}

// =====================
// Resume Tailoring
// =====================

function initTailor() {
  elements.tailorBtn.addEventListener('click', tailorResume);
  elements.copyResult.addEventListener('click', copyToClipboard);
  elements.downloadResult.addEventListener('click', downloadResult);
  elements.downloadPdf.addEventListener('click', () => {
    if (!compiledPdfUrl) return;
    window.open(compiledPdfUrl, '_blank');
  });
}

async function tailorResume() {
  const jobDescription = elements.jobDescription.value.trim();
  
  if (!jobDescription) {
    showToast('Please enter a job description', 'error');
    return;
  }
  
  // Check if resume is loaded
  try {
    const statusResponse = await fetch(`${API_BASE}/current-resume`);
    const statusData = await statusResponse.json();
    
    if (!statusData.loaded) {
      showToast('Please upload a resume first', 'error');
      // Switch to upload tab
      elements.tabs.forEach(t => t.classList.remove('active'));
      elements.tabContents.forEach(c => c.classList.remove('active'));
      document.querySelector('[data-tab="upload"]').classList.add('active');
      document.getElementById('uploadTab').classList.add('active');
      return;
    }
  } catch (error) {
    showToast('Cannot connect to server', 'error');
    return;
  }
  
  // Show loading state
  elements.tailorBtn.disabled = true;
  elements.loading.classList.remove('hidden');
  elements.result.classList.add('hidden');
  
  try {
    const response = await fetch(`${API_BASE}/tailor`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ job_description: jobDescription })
    });
    
    const data = await response.json();
    
    if (data.error) {
      showToast(data.error, 'error');
      return;
    }
    
    // Display result
    currentTailoredContent = data.tailored_resume;
    currentFileType = data.file_type;
    elements.resultContent.textContent = currentTailoredContent;
    elements.result.classList.remove('hidden');

    if (data.compiled_pdf_url) {
      compiledPdfUrl = `${API_BASE}${data.compiled_pdf_url}`;
      elements.downloadPdf.classList.remove('hidden');
    } else {
      compiledPdfUrl = '';
      elements.downloadPdf.classList.add('hidden');
    }

    // Show appropriate success message with fill ratio info
    let successMsg = 'Resume tailored successfully!';
    const fillInfo = data.fill_ratio ? ` (${Math.round(data.fill_ratio * 100)}% filled)` : '';
    
    if (data.was_adjusted && data.adjustment_type) {
      const action = data.adjustment_type === 'expanded' ? 'expanded' : 'shortened';
      successMsg = `Resume ${action} ${data.adjustment_count}x${fillInfo}`;
    } else {
      successMsg = `Resume tailored!${fillInfo}`;
    }
    
    if (data.page_count && data.page_count > 1) {
      successMsg = `Resume is ${data.page_count} pages (couldn't fit on 1)`;
      showToast(successMsg, 'error');
    } else if (data.fill_ratio && (data.fill_ratio < 0.88 || data.fill_ratio > 0.96)) {
      showToast(`${successMsg} - fill ratio outside ideal range`, 'info');
    } else {
      showToast(successMsg, 'success');
    }
    
  } catch (error) {
    console.error('Tailor error:', error);
    showToast('Failed to tailor resume. Please try again.', 'error');
  } finally {
    elements.tailorBtn.disabled = false;
    elements.loading.classList.add('hidden');
  }
}

async function copyToClipboard() {
  try {
    await navigator.clipboard.writeText(currentTailoredContent);
    showToast('Copied to clipboard!', 'success');
  } catch (error) {
    showToast('Failed to copy', 'error');
  }
}

function downloadResult() {
  if (!currentTailoredContent) return;
  
  const extension = currentFileType === 'tex' ? '.tex' : '.txt';
  const mimeType = currentFileType === 'tex' ? 'application/x-tex' : 'text/plain';
  const filename = `tailored_resume${extension}`;
  
  const blob = new Blob([currentTailoredContent], { type: mimeType });
  const url = URL.createObjectURL(blob);
  
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
  
  showToast('Download started!', 'success');
}

// =====================
// RAG Context
// =====================

function initContext() {
  elements.loadContext.addEventListener('click', loadRagContext);
  elements.saveContext.addEventListener('click', saveRagContext);
}

async function loadRagContext() {
  try {
    const response = await fetch(`${API_BASE}/rag-context`);
    const data = await response.json();
    
    if (data.context) {
      elements.ragContext.value = data.context;
      showToast('Context loaded from server', 'success');
    } else {
      elements.ragContext.value = '';
      showToast('No context found on server', 'info');
    }
  } catch (error) {
    console.error('Load context error:', error);
    showToast('Failed to load context', 'error');
  }
}

async function saveRagContext() {
  const context = elements.ragContext.value;
  
  try {
    const response = await fetch(`${API_BASE}/rag-context`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ context })
    });
    
    const data = await response.json();
    
    if (data.success) {
      showToast('Context saved successfully!', 'success');
    } else {
      showToast(data.error || 'Failed to save context', 'error');
    }
  } catch (error) {
    console.error('Save context error:', error);
    showToast('Failed to save context', 'error');
  }
}

// =====================
// Initialization
// =====================

async function init() {
  // Check server health
  await checkServerHealth();
  
  // Initialize all components
  initTabs();
  initDropzone();
  initTailor();
  initContext();
  
  // Update resume status
  updateResumeStatus();
  
  // Periodic health check
  setInterval(checkServerHealth, 30000);
}

// Start the app
document.addEventListener('DOMContentLoaded', init);

