/**
 * DataForge — Workspace Logic
 */

document.addEventListener('alpine:init', () => {
  Alpine.data('workspace', () => ({
    activeTab: 'datetime',
    fileId: null,
    files: [],
    previewData: [],
    displayColumns: [],
    totalRows: 0,
    isExporting: false,
    exportFormat: '',
    searchQuery: '',
    quality: { complete_rows_pct: 0, problematic_cols_count: 0 },

    currentPage: 1,
    pageSize: 20,

    aggregationResult: [],
    aggregationColumns: [],
    comparisonResult: [],
    comparisonColumns: [],
    chartImageBase64: null,

    // Cached column lists (refreshed after load)
    availableColumns: [],
    numericColumns: [],
    categoryColumns: [],

    // Sheet inclusion toggles for XLSX export
    includeAggregation: true,
    includeComparison: true,
    includeChart: true,

    // Tools State
    tools: {
      datetime: { dateCol: '', timeCol: '', format: 'YYYY-MM-DD HH:MM:SS', dropOriginal: true },
      aggregate: { columns: [], types: ['SUM', 'AVG'], groupBy: '', searchCol: '' },
      compare: { colA: '', colB: '', calcType: 'pct_diff', resultName: 'persen_selisih' },
      chart: { source: 'original', type: 'bar', xCol: '', yCol: '' }
    },

    chartInstance: null,


    refreshColumnLists() {
      if (this.files.length === 0) return;
      const cols = this.files[0].metadata.columns;
      this.availableColumns = cols.map(c => c.name);
      this.numericColumns = cols.filter(c => c.type === 'num').map(c => c.name);
      this.categoryColumns = cols.filter(c => c.type === 'str' || c.type === 'date').map(c => c.name);
    },


    get totalPages() {
      if (this.totalRows <= 0) return 0;
      return Math.ceil(this.totalRows / this.pageSize);
    },

    get visiblePages() {
      const total = this.totalPages;
      if (total <= 0) return [];
      
      let pages = [];
      if (total <= 5) {
        for (let i = 1; i <= total; i++) pages.push(i);
      } else {
        if (this.currentPage <= 3) {
          pages = [1, 2, 3, 4, 5];
        } else if (this.currentPage >= total - 2) {
          pages = [total - 4, total - 3, total - 2, total - 1, total];
        } else {
          pages = [this.currentPage - 2, this.currentPage - 1, this.currentPage, this.currentPage + 1, this.currentPage + 2];
        }
      }
      return pages;
    },

    async init() {
      // Get file_id from URL
      const urlParams = new URLSearchParams(window.location.search);
      this.fileId = urlParams.get('file_id');
      const presetId = urlParams.get('preset');
      
      if (this.fileId) {
        await this.loadPreview();
        // If preset requested, apply it after preview is loaded
        if (presetId) {
            await this.loadPreset(presetId);
        }
      } else {
        Toast.error("Tidak ada file yang dipilih.");
      }
    },

    async loadPreset(presetId) {
      try {
        const response = await fetch(`/presets/api/`);
        const presets = await response.json();
        const preset = presets.find(p => String(p.id) === String(presetId));
        
        if (!preset) {
            Toast.error("Preset tidak ditemukan.");
            return;
        }

        // Apply column config
        if (preset.column_config && preset.column_config.length > 0) {
            const savedCols = preset.column_config[0].columns;
            if (this.files.length > 0) {
                this.files[0].metadata.columns.forEach(c => {
                    const savedC = savedCols.find(x => x.name === c.name);
                    if (savedC) {
                        c.selected = savedC.include;
                    }
                });
                this.updateDisplayColumns();
            }
        }

        // Apply tools config
        if (preset.datetime_config) {
            Object.assign(this.tools.datetime, preset.datetime_config);
        }
        if (preset.export_config) {
            if (preset.export_config.aggregate) {
                Object.assign(this.tools.aggregate, preset.export_config.aggregate);
            }
            if (preset.export_config.compare) {
                Object.assign(this.tools.compare, preset.export_config.compare);
            }
        }
        
        Toast.success(`Preset "${preset.name}" berhasil diterapkan!`);
        
        // Clean URL so refresh doesn't re-apply
        window.history.replaceState({}, '', `/workspace/?file_id=${this.fileId}`);
      } catch (e) {
          console.error(e);
          Toast.error("Gagal memuat preset.");
      }
    },

    async loadPreview(page = 1) {
      try {
        this.currentPage = page;
        const response = await fetch(`/api/files/${this.fileId}/preview/?page=${page}&page_size=${this.pageSize}`);
        const data = await response.json();
        
        if (response.ok) {
          // Initialize columns selection state if not already initialized
          const columns = data.columns.map(c => ({
            ...c,
            selected: true // By default, select all
          }));
          
          if (this.files.length === 0) {
              this.files = [{
                id: this.fileId,
                filename: data.original_filename || "File Terupload",
                expanded: true,
                metadata: {
                  ...data,
                  columns: columns
                }
              }];
          } else {
              // Always update columns so Compare/Aggregasi dropdowns stay in sync
              this.files[0].metadata.columns = columns;
          }
          
          this.totalRows = data.row_count;
          this.previewData = data.preview || [];
          this.quality = data.quality || { complete_rows_pct: 100, problematic_cols_count: 0 };
          this.refreshColumnLists();
          this.updateDisplayColumns();
        } else {
          Toast.error(data.error || "Gagal memuat preview data");
        }
      } catch (e) {
        console.error(e);
        Toast.error("Kesalahan jaringan saat memuat preview");
      }
    },

    async changePage(page) {
        if (page < 1 || page > this.totalPages) return;
        await this.loadPreview(page);
        // Scroll table to top
        document.querySelector('.q-table-wrap').scrollTop = 0;
    },

    updateDisplayColumns() {
      if (this.files.length > 0) {
        this.displayColumns = this.files[0].metadata.columns
          .filter(c => c.selected)
          .map(c => c.name);
      }
    },

    selectAll() {
      if (this.files.length > 0) {
        this.files[0].metadata.columns.forEach(c => c.selected = true);
        this.updateDisplayColumns();
        Toast.info('Semua kolom dipilih');
      }
    },
    
    deselectAll() {
      if (this.files.length > 0) {
        this.files[0].metadata.columns.forEach(c => c.selected = false);
        this.updateDisplayColumns();
        Toast.info('Semua kolom dihapus');
      }
    },

    toggleColumn(fileId, colName, isChecked) {
      this.updateDisplayColumns();
    },

    async exportData(format) {
      if (!this.fileId) return;
      this.isExporting = true;
      this.exportFormat = format;
      
      Toast.info(`Mempersiapkan ekspor ${format.toUpperCase()}...`);
      
      // Get selected columns
      const selectedColumns = this.files[0].metadata.columns
        .map(c => ({
          name: c.name,
          include: c.selected
        }));
        
      try {
        const csrfTokenDoc = document.querySelector('[name=csrfmiddlewaretoken]');
        const headers = {'Content-Type': 'application/json'};
        if (csrfTokenDoc) {
          headers['X-CSRFToken'] = csrfTokenDoc.value;
        }

        const response = await fetch('/api/export/', {
          method: 'POST',
          headers: headers,
          body: JSON.stringify({
            file_ids: [this.fileId],
            format: format,
            columns: selectedColumns,
            aggregation_result: this.aggregationResult,
            aggregation_columns: this.aggregationColumns,
            comparison_result: this.comparisonResult,
            comparison_columns: this.comparisonColumns,
            include_aggregation: this.includeAggregation,
            include_comparison: this.includeComparison
          })
        });
        
        const data = await response.json();
        
        if (response.ok && data.url) {
          Toast.success(`Ekspor ${format.toUpperCase()} berhasil!`);
          
          try {
            const fileResponse = await fetch(data.url);
            const blob = await fileResponse.blob();
            
            // Clean filename
            let baseName = "Data_Export";
            if (this.files[0].metadata && this.files[0].metadata.original_filename) {
               baseName = this.files[0].metadata.original_filename.split('.')[0];
            }
            const suggestedName = `${baseName}_processed.${format}`;
            
            // Try to use the modern File System Access API for "Save As" dialogue
            if (window.showSaveFilePicker) {
              try {
                const handle = await window.showSaveFilePicker({
                  suggestedName: suggestedName,
                  types: [{
                    description: format === 'xlsx' ? 'Excel File' : 'CSV File',
                    accept: format === 'xlsx' 
                      ? { 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': ['.xlsx'] } 
                      : { 'text/csv': ['.csv'] },
                  }],
                });
                const writable = await handle.createWritable();
                await writable.write(blob);
                await writable.close();
                return; // successfully saved
              } catch (err) {
                if (err.name === 'AbortError') return; // User cancelled
                console.error('File System API failed, falling back:', err);
              }
            }
            
            // Fallback for browsers that don't support showSaveFilePicker (or if it fails)
            const userFilename = prompt("Simpan file sebagai:", suggestedName);
            if (!userFilename) return; // User cancelled
            
            const blobUrl = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.style.display = 'none';
            a.href = blobUrl;
            
            // Ensure filename ends with correct extension
            let finalName = userFilename;
            if (!finalName.toLowerCase().endsWith(`.${format}`)) {
                finalName += `.${format}`;
            }
            a.download = finalName;
            
            document.body.appendChild(a);
            a.click();
            
            setTimeout(() => {
              window.URL.revokeObjectURL(blobUrl);
              document.body.removeChild(a);
            }, 100);
          } catch(e) {
            console.error(e);
            Toast.error("Gagal memproses unduhan (Download).");
            window.location.href = data.url; // Fallback
          }
        } else {
          Toast.error("Gagal mengekspor file: " + (data.error || "Unknown error"));
        }
      } catch (e) {
        console.error(e);
        Toast.error("Terjadi kesalahan jaringan saat ekspor.");
      } finally {
        this.isExporting = false;
        this.exportFormat = '';
      }
    },

    async applyAggregation() {
      if (!this.fileId) return;
      if (this.tools.aggregate.columns.length === 0 || this.tools.aggregate.types.length === 0) {
        Toast.warning("Pilih kolom dan jenis agregasi terlebih dahulu.");
        return;
      }

      Toast.info("Menghitung agregasi...");
      try {
        const response = await fetch('/api/processor/aggregate/', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value
          },
          body: JSON.stringify({
            file_id: this.fileId,
            columns: this.tools.aggregate.columns,
            types: this.tools.aggregate.types,
            group_by: this.tools.aggregate.groupBy
          })
        });

        const data = await response.json();
        if (response.ok) {
          this.aggregationResult = data.data;
          this.aggregationColumns = data.columns;
          Toast.success("Agregasi berhasil! Hasil ringkasan muncul di panel tepat di atas tabel preview.");
          // Switch to a view that shows the result or scroll to it
        } else {
          Toast.error(data.error || "Gagal menghitung agregasi");
        }
      } catch (e) {
        console.error(e);
        Toast.error("Terjadi kesalahan jaringan.");
      }
    },
    
    downloadAggregation() {
      if (this.aggregationResult.length === 0) return;
      
      Toast.info("Mengunduh hasil agregasi...");
      
      // Convert to CSV
      const headers = this.aggregationColumns.join(',');
      const rows = this.aggregationResult.map(row => 
        this.aggregationColumns.map(col => {
          let val = row[col];
          if (typeof val === 'string' && val.includes(',')) return `"${val}"`;
          return val;
        }).join(',')
      );
      
      const csvContent = "data:text/csv;charset=utf-8," + headers + "\n" + rows.join("\n");
      const encodedUri = encodeURI(csvContent);
      const link = document.createElement("a");
      link.setAttribute("href", encodedUri);
      link.setAttribute("download", `aggregation_result_${this.fileId}.csv`);
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      
      Toast.success("Hasil agregasi berhasil diunduh.");
    },


    async applyComparison() {
      if (!this.fileId) return;
      if (!this.tools.compare.colA || !this.tools.compare.colB) {
        Toast.warning("Pilih kolom A dan kolom B terlebih dahulu.");
        return;
      }

      Toast.info("Memproses perbandingan...");
      try {
        const response = await fetch('/api/processor/compare/', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value
          },
          body: JSON.stringify({
            file_id: this.fileId,
            col_a: this.tools.compare.colA,
            col_b: this.tools.compare.colB,
            calc_type: this.tools.compare.calcType,
            result_name: this.tools.compare.resultName
          })
        });

        const data = await response.json();
        if (response.ok) {
          // Store comparison results for multi-sheet export
          this.comparisonResult = data.data || [];
          this.comparisonColumns = data.columns || [];
          Toast.success(data.message + ' — Hasil tersedia untuk export XLSX.');
          // Reload preview with the new processed file
          this.fileId = data.new_file_id;
          window.history.replaceState({}, '', `/workspace/?file_id=${data.new_file_id}`);
          this.files = [];
          await this.loadPreview();
        } else {
          Toast.error(data.error || "Gagal memproses perbandingan");
        }
      } catch (e) {
        console.error(e);
        Toast.error("Terjadi kesalahan jaringan.");
      }
    },

    generateChart() {
      if (!this.tools.chart.xCol || !this.tools.chart.yCol) {
        Toast.warning("Pilih Kolom X dan Kolom Y terlebih dahulu.");
        return;
      }

      let dataSource = this.tools.chart.source === 'agregasi' ? this.aggregationResult : this.previewData;
      if (!dataSource || dataSource.length === 0) {
        Toast.warning("Data kosong.");
        return;
      }

      // Extract labels and data
      const labels = dataSource.map(row => {
        let val = row[this.tools.chart.xCol];
        return (val === null || val === undefined || val === '') ? 'N/A' : String(val);
      });
      const chartData = dataSource.map(row => parseFloat(row[this.tools.chart.yCol]) || 0);

      const ctx = document.getElementById('chart-preview').getContext('2d');
      if (this.chartInstance) {
        this.chartInstance.destroy();
      }

      // Palet warna yang selaras dengan DataForge
      const bgColors = [
        'rgba(16, 185, 129, 0.7)',
        'rgba(59, 130, 246, 0.7)',
        'rgba(245, 158, 11, 0.7)',
        'rgba(239, 68, 68, 0.7)',
        'rgba(139, 92, 246, 0.7)',
        'rgba(6, 182, 212, 0.7)'
      ];

      // Register DataLabels plugin
      Chart.register(ChartDataLabels);

      this.chartInstance = new Chart(ctx, {
        type: this.tools.chart.type,
        data: {
          labels: labels,
          datasets: [{
            label: this.tools.chart.yCol,
            data: chartData,
            backgroundColor: this.tools.chart.type === 'pie' ? bgColors : bgColors[0],
            borderColor: this.tools.chart.type === 'pie' ? '#1f2937' : 'rgba(16, 185, 129, 1)',
            borderWidth: 1
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          color: '#cbd5e1',
          scales: this.tools.chart.type === 'pie' ? {} : {
            x: { ticks: { color: '#94a3b8' }, grid: { color: 'rgba(255,255,255,0.05)' } },
            y: { ticks: { color: '#94a3b8' }, grid: { color: 'rgba(255,255,255,0.05)' } }
          },
          plugins: {
            legend: {
              display: this.tools.chart.type === 'pie',
              position: 'right',
              labels: { color: '#cbd5e1' }
            },
            datalabels: {
              display: this.tools.chart.type === 'pie',
              color: '#ffffff',
              font: { weight: 'bold', size: 11 },
              formatter: (value, context) => {
                const dataset = context.chart.data.datasets[0];
                const total = dataset.data.reduce((acc, curr) => acc + curr, 0);
                if (total === 0) return '0%';
                const percentage = ((value / total) * 100).toFixed(1);
                return percentage + '%';
              }
            }
          }
        }
      });

      // Beri sedikit delay agar chart selesai menggambar animasi sebelum nge-capture image.
      setTimeout(() => {
        this.captureChart();
      }, 800);
    },

    captureChart() {
      const canvas = document.getElementById('chart-preview');
      if (canvas) {
        this.chartImageBase64 = canvas.toDataURL('image/png');
        Toast.success('Grafik telah dibuat.');
      }
    },

    async saveAsPreset() {
      const name = prompt("Masukkan nama preset:");
      if (!name) return;
      
      const description = prompt("Masukkan deskripsi (opsional):");
      
      const payload = {
        name: name,
        description: description,
        column_config: this.files.map(f => ({
          file_id: f.id,
          columns: (f.metadata.columns || []).map(c => ({
            name: c.name,
            alias: c.alias || c.name,
            include: c.selected !== false // default to true if selected is undefined
          }))
        })),
        datetime_config: this.tools.datetime,
        export_config: {
          format: 'xlsx',
          aggregate: this.tools.aggregate,
          compare: this.tools.compare
        }
      };

      try {
        const response = await fetch('/presets/api/', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': this.getCsrfToken()
          },
          body: JSON.stringify(payload)
        });

        if (response.ok) {
          Toast.success("Preset berhasil disimpan!");
        } else {
          Toast.error("Gagal menyimpan preset.");
        }
      } catch (e) {
        Toast.error("Terjadi kesalahan jaringan.");
      }
    },

    getCsrfToken() {
      const token = document.querySelector('[name=csrfmiddlewaretoken]')?.value;
      if (token) return token;
      return document.cookie.split('; ')
        .find(row => row.startsWith('csrftoken='))
        ?.split('=')[1];
    },

    downloadChart() {
      if (!this.chartInstance) {
        Toast.warning("Belum ada grafik yang dibuat.");
        return;
      }
      
      const canvas = document.getElementById('chart-preview');
      
      const tempCanvas = document.createElement('canvas');
      tempCanvas.width = canvas.width;
      tempCanvas.height = canvas.height;
      const ctx = tempCanvas.getContext('2d');
      // Beri background gelap agar teks terlihat
      ctx.fillStyle = '#1e293b'; 
      ctx.fillRect(0, 0, tempCanvas.width, tempCanvas.height);
      ctx.drawImage(canvas, 0, 0);

      const link = document.createElement('a');
      link.download = `Grafik_${this.tools.chart.yCol}_vs_${this.tools.chart.xCol}.png`;
      link.href = tempCanvas.toDataURL('image/png');
      link.click();
      
      Toast.success("Grafik berhasil diunduh.");
    }
  }));
});

document.addEventListener('DOMContentLoaded', () => {
  // Chart initialization and other global logic can be maintained here if needed
});
