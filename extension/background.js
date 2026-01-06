/**
 * Resume Tailorer - Background Service Worker
 * Handles background tasks and message passing
 */

// Listen for installation
chrome.runtime.onInstalled.addListener((details) => {
  if (details.reason === 'install') {
    console.log('Resume Tailorer extension installed!');
  } else if (details.reason === 'update') {
    console.log('Resume Tailorer extension updated!');
  }
});

// Handle messages from popup or content scripts
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.type === 'HEALTH_CHECK') {
    fetch('http://localhost:5000/health')
      .then(response => response.json())
      .then(data => sendResponse({ status: 'connected', data }))
      .catch(error => sendResponse({ status: 'disconnected', error: error.message }));
    return true; // Keep message channel open for async response
  }
  
  if (message.type === 'OPEN_OPTIONS') {
    chrome.runtime.openOptionsPage();
    sendResponse({ success: true });
  }
  
  return false;
});

// Log errors
self.addEventListener('error', (event) => {
  console.error('Background script error:', event.error);
});

