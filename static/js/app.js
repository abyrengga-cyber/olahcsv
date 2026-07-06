/**
 * DataForge — Core Application Logic
 * Toast notifications, Alpine.js components, utilities
 */

// ─── Toast Notification System ───────────────────────────────────
const Toast = {
  container: null,

  init() {
    this.container = document.getElementById('toast-container');
  },

  show(message, type = 'info', duration = 4000) {
    if (!this.container) this.init();

    const icons = {
      success: '✓',
      error: '✕',
      warning: '⚠',
      info: 'ℹ'
    };

    const toast = document.createElement('div');
    toast.className = `q-toast q-toast--${type}`;

    const iconSpan = document.createElement('span');
    iconSpan.className = 'q-toast__icon';
    iconSpan.textContent = icons[type] || icons.info;

    const textSpan = document.createElement('span');
    textSpan.className = 'q-toast__text';
    textSpan.textContent = message;

    const closeBtn = document.createElement('button');
    closeBtn.className = 'q-toast__close';
    closeBtn.textContent = '\u00D7';
    closeBtn.onclick = () => toast.remove();

    toast.appendChild(iconSpan);
    toast.appendChild(textSpan);
    toast.appendChild(closeBtn);

    this.container.appendChild(toast);

    setTimeout(() => {
      toast.style.animation = 'toastOut 0.4s ease forwards';
      setTimeout(() => toast.remove(), 400);
    }, duration);
  },

  success(msg) { this.show(msg, 'success'); },
  error(msg) { this.show(msg, 'error'); },
  warning(msg) { this.show(msg, 'warning'); },
  info(msg) { this.show(msg, 'info'); }
};

// ─── Alpine.js Components ────────────────────────────────────────

// Upload Zone Component
function uploadZone() {
  return {
    dragover: false,
    files: [],

    handleDrop(event) {
      this.dragover = false;
      const droppedFiles = Array.from(event.dataTransfer.files);
      this.processFiles(droppedFiles);
    },

    handleFiles(event) {
      const selectedFiles = Array.from(event.target.files);
      this.processFiles(selectedFiles);
    },

    async processFiles(fileList) {
      const validExtensions = ['.csv', '.txt', '.xlsx'];
      const maxSize = 50 * 1024 * 1024; // 50MB

      const validFiles = [];
      const errors = [];

      fileList.forEach(file => {
        const ext = '.' + file.name.split('.').pop().toLowerCase();
        if (!validExtensions.includes(ext)) {
          errors.push(`${file.name}: Format tidak didukung`);
          return;
        }
        if (file.size > maxSize) {
          errors.push(`${file.name}: Ukuran melebihi 50MB`);
          return;
        }
        validFiles.push(file);
      });

      errors.forEach(err => Toast.error(err));

      if (validFiles.length > 0) {
        Toast.info('Mengunggah file...');
        const formData = new FormData();
        validFiles.forEach(file => formData.append('file', file));

        try {
          // Send request with CSRF token if available
          const csrfTokenDoc = document.querySelector('[name=csrfmiddlewaretoken]');
          const headers = {};
          if (csrfTokenDoc) {
            headers['X-CSRFToken'] = csrfTokenDoc.value;
          }

          const response = await fetch('/api/v1/files/upload/', {
            method: 'POST',
            body: formData,
            headers: headers
          });

          const data = await response.json();
          if (response.ok && data.files.length > 0) {
            Toast.success(`${validFiles.length} file berhasil diunggah & diproses`);
            setTimeout(() => {
              window.location.href = `/workspace/?file_id=${data.files[0].id}`;
            }, 1000);
          } else {
            Toast.error('Gagal mengunggah file.');
          }
        } catch (error) {
          console.error(error);
          Toast.error('Terjadi kesalahan jaringan.');
        }
      }
    }
  };
}

// ─── Initialize ──────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  Toast.init();
});
