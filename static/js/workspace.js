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
    isLoading: false,
    isExporting: false,
    exportFormat: '',
    searchQuery: '',
    quality: { complete_rows_pct: 0, problematic_cols_count: 0 },

    currentPage: 1,
    pageSize: 20,
    sortColumn: null,
    sortOrder: null,
    sortVersion: 0,
    filters: [{ col: '', op: 'contains', query: '', values: [] }],
    filterLogic: 'AND',

    aggregationResult: [],
    aggregationColumns: [],
    comparisonResult: [],
    comparisonColumns: [],

    // Cached column lists (refreshed after load)
    availableColumns: [],
    numericColumns: [],
    categoryColumns: [],

    // Sheet inclusion toggles for XLSX export
    includeAggregation: true,
    includeComparison: true,
    includeChart: true,

    // Export scope: 'all' = full data, 'filtered' = only filtered rows
    exportScope: 'all',

    // Tools State
    tools: {
      datetime: { dateCol: '', timeCol: '', format: 'YYYY-MM-DD HH:MM:SS', dropOriginal: true },
      aggregate: { columns: [], types: ['SUM', 'AVG'], groupBy: '', searchCol: '' },
      compare: { colA: '', colB: '', calcType: 'pct_diff', resultName: 'persen_selisih' },
      chart: { source: 'original', type: 'bar', xCol: '', yCol: '' }
    },

    chartInstance: null,
    _sortableInstance: null,

    STORAGE_KEY: 'dataforge_workspace_state',

    // Undo / Redo
    _history: [],
    _historyIndex: -1,
    _historyMax: 50,

    get canUndo() {
      return this._historyIndex > 0;
    },

    get canRedo() {
      return this._historyIndex < this._history.length - 1;
    },

    _captureSnapshot() {
      const cols = this.files[0]?.metadata.columns;
      if (!cols) return null;
      return {
        columns: cols.map(c => ({ name: c.name, selected: c.selected }))
      };
    },

    _pushHistory() {
      const snap = this._captureSnapshot();
      if (!snap) return;
      // Truncate any redo entries beyond current index
      this._history = this._history.slice(0, this._historyIndex + 1);
      this._history.push(snap);
      if (this._history.length > this._historyMax) {
        this._history.shift();
      }
      this._historyIndex = this._history.length - 1;
    },

    _applySnapshot(snap) {
      if (!snap || !this.files[0]) return;
      const cols = this.files[0].metadata.columns;
      // Restore selection state, preserving order from snapshot
      const newCols = snap.columns.map(s => {
        const existing = cols.find(c => c.name === s.name);
        return existing ? { ...existing, selected: s.selected } : null;
      }).filter(Boolean);
      // Append any columns in current data not in snapshot (shouldn't happen, but safe)
      cols.forEach(c => {
        if (!newCols.find(n => n.name === c.name)) {
          newCols.push(c);
        }
      });
      this.files[0].metadata.columns = newCols;
      this.refreshColumnLists();
      this.updateDisplayColumns();
      this._initColumnSortable();
    },

    undo() {
      if (!this.canUndo) return;
      this._historyIndex--;
      this._applySnapshot(this._history[this._historyIndex]);
      Toast.info('Undo');
    },

    redo() {
      if (!this.canRedo) return;
      this._historyIndex++;
      this._applySnapshot(this._history[this._historyIndex]);
      Toast.info('Redo');
    },

    _filterQueryString() {
      const active = this.filters.filter(f => f.col && f.query);
      if (active.length === 0) return '';
      return '&filters=' + encodeURIComponent(JSON.stringify(active.map(f => ({ col: f.col, op: f.op, query: f.query })))) + '&filter_logic=' + encodeURIComponent(this.filterLogic);
    },

    _saveState() {
      const state = {
        fileId: this.fileId,
        tools: this.tools,
        exportScope: this.exportScope,
        includeAggregation: this.includeAggregation,
        includeComparison: this.includeComparison,
        pageSize: this.pageSize,
        filters: this.filters.map(f => ({ col: f.col, op: f.op, query: f.query })),
        filterLogic: this.filterLogic,
        sortColumn: this.sortColumn,
        sortOrder: this.sortOrder,
        columnSelections: this.files[0]?.metadata.columns.map(c => ({ name: c.name, selected: c.selected })),
      };
      try {
        sessionStorage.setItem(this.STORAGE_KEY, JSON.stringify(state));
      } catch (e) { /* quota exceeded, ignore */ }
    },

    _restoreState() {
      try {
        const raw = sessionStorage.getItem(this.STORAGE_KEY);
        if (!raw) return;
        const saved = JSON.parse(raw);
        const urlParams = new URLSearchParams(window.location.search);
        const currentFileId = urlParams.get('file_id');
        const sameFile = saved.fileId && saved.fileId === currentFileId;
      if (saved.tools) {
        if (saved.tools.datetime) Object.assign(this.tools.datetime, saved.tools.datetime);
        if (saved.tools.aggregate) Object.assign(this.tools.aggregate, saved.tools.aggregate);
        if (saved.tools.compare) Object.assign(this.tools.compare, saved.tools.compare);
        if (saved.tools.chart) Object.assign(this.tools.chart, saved.tools.chart);
      }
      if (saved.exportScope) this.exportScope = saved.exportScope;
      if (saved.includeAggregation !== undefined) this.includeAggregation = saved.includeAggregation;
      if (saved.includeComparison !== undefined) this.includeComparison = saved.includeComparison;
      if (saved.pageSize) this.pageSize = saved.pageSize;
      if (sameFile) {
        if (saved.filters) {
          this.filters = saved.filters.map(f => ({ ...f, values: [] }));
        } else {
          if (saved.filterColumn) this.filters[0].col = saved.filterColumn;
          if (saved.filterOp) this.filters[0].op = saved.filterOp;
          if (saved.filterQuery) this.filters[0].query = saved.filterQuery;
          if (saved.filterColumn2) {
            if (this.filters.length < 2) this.filters.push({ col: '', op: 'contains', query: '', values: [] });
            this.filters[1].col = saved.filterColumn2;
            if (saved.filterOp2) this.filters[1].op = saved.filterOp2;
            if (saved.filterQuery2) this.filters[1].query = saved.filterQuery2;
          }
        }
        if (saved.filterLogic) this.filterLogic = saved.filterLogic;
        if (saved.sortColumn) this.sortColumn = saved.sortColumn;
        if (saved.sortOrder) this.sortOrder = saved.sortOrder;
      }
      this._pendingColumnSelections = saved.columnSelections || null;
      } catch (e) { /* corrupted data, ignore */ }
    },

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

    toggleSort(colName) {
      let order;
      if (this.sortColumn === colName) {
        if (this.sortOrder === 'asc') {
          order = 'desc';
        } else {
          this.loadPreview(this.currentPage);
          return;
        }
      } else {
        order = 'asc';
      }
      this.sortColumn = colName;
      this.sortOrder = order;
      this.sortVersion++;
      this._fetchSortedPreview();
    },

    async _fetchSortedPreview() {
      if (!this.fileId || !this.sortColumn) return;
      try {
        let url = `/api/v1/files/${this.fileId}/preview/?page=${this.currentPage}&page_size=${this.pageSize}&sort_by=${encodeURIComponent(this.sortColumn)}&sort_order=${this.sortOrder}`;
        url += this._filterQueryString();
        const response = await fetch(url);
        const data = await response.json();
        if (response.ok) {
          this.previewData = data.preview || [];
          this.totalRows = data.row_count;
          this.quality = data.quality || { complete_rows_pct: 100, problematic_cols_count: 0 };
          this._afterRender();
        }
      } catch (e) {
        console.error(e);
      }
    },

    _initColumnSortable() {
      Alpine.nextTick(() => {
        const el = Array.isArray(this.$refs.columnList) ? this.$refs.columnList[0] : this.$refs.columnList;
        if (!el) return;
        if (this._sortableInstance) {
          this._sortableInstance.destroy();
        }
        this._sortableInstance = new Sortable(el, {
          handle: '.q-col-tree__col',
          animation: 150,
          ghostClass: 'q-col-tree__col--ghost',
          onEnd: (evt) => {
            const cols = this.files[0]?.metadata.columns;
            if (!cols) return;
            this._pushHistory();
            const [moved] = cols.splice(evt.oldIndex, 1);
            cols.splice(evt.newIndex, 0, moved);
            this.updateDisplayColumns();
            this._saveState();
          },
        });
      });
    },

    _cellValue(val) {
      return (val === null || val === undefined || val === '') ? '\u2014' : val;
    },
    _cellEmpty(val) {
      return (val === null || val === undefined || val === '') ? 'cell-empty' : '';
    },
    _afterRender() {
      setTimeout(() => this._updateCustomTopScrollbar(), 0);
    },

    _updateCustomTopScrollbar() {
      try {
        const wrap = document.querySelector('#preview-table-wrap');
        const thumb = document.querySelector('.q-scrollbar-top__thumb');
        const topBar = document.querySelector('.q-scrollbar-top');
        if (!wrap || !thumb || !topBar) return;
        const scrollRange = wrap.scrollWidth - wrap.clientWidth;
        const barWidth = topBar.clientWidth;
        if (scrollRange <= 0 || barWidth <= 0) {
          thumb.style.width = '100%';
          thumb.style.left = '0';
          return;
        }
        const ratio = wrap.clientWidth / wrap.scrollWidth;
        const thumbWidth = Math.max(ratio * barWidth, 60);
        const maxLeft = barWidth - thumbWidth;
        const pos = (wrap.scrollLeft / scrollRange) * maxLeft;
        thumb.style.width = Math.min(thumbWidth, barWidth) + 'px';
        thumb.style.left = Math.max(0, Math.min(pos, maxLeft)) + 'px';
      } catch(e) {
        console.error('DataForge: _updateCustomTopScrollbar error', e);
      }
    },

    _initTopScrollbarDrag() {
      const thumb = document.querySelector('.q-scrollbar-top__thumb');
      const topBar = document.querySelector('.q-scrollbar-top');
      if (!thumb || !topBar) return;

      const onMouseDown = (e) => {
        e.preventDefault();
        e.stopPropagation();
        const startX = e.clientX;
        const startLeft = parseFloat(thumb.style.left) || 0;
        const barWidth = topBar.clientWidth;
        const wrap = document.querySelector('#preview-table-wrap');
        if (!wrap) return;

        const onMouseMove = (e) => {
          const deltaX = e.clientX - startX;
          const scrollRange = wrap.scrollWidth - wrap.clientWidth;
          if (scrollRange <= 0) return;
          const ratio = wrap.clientWidth / wrap.scrollWidth;
          const thumbWidth = Math.max(ratio * barWidth, 60);
          const maxLeft = barWidth - thumbWidth;
          const newLeft = Math.max(0, Math.min(maxLeft, startLeft + deltaX));
          const newScrollLeft = (newLeft / maxLeft) * scrollRange;
          wrap.scrollLeft = newScrollLeft;
        };

        const onMouseUp = () => {
          document.removeEventListener('mousemove', onMouseMove);
          document.removeEventListener('mouseup', onMouseUp);
          document.body.style.userSelect = '';
        };

        document.body.style.userSelect = 'none';
        document.addEventListener('mousemove', onMouseMove);
        document.addEventListener('mouseup', onMouseUp);
      };

      thumb.addEventListener('mousedown', onMouseDown);
    },

    async init() {
      Chart.register(ChartDataLabels);
      this._csrfToken = document.querySelector('[name=csrfmiddlewaretoken]')?.value;
      this._restoreState();

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

      // Custom top scrollbar (visual proxy for bottom scrollbar)
      setTimeout(() => {
        const wrap = document.querySelector('#preview-table-wrap');
        const topBar = document.querySelector('.q-scrollbar-top');
        if (wrap && topBar) {
          this._updateCustomTopScrollbar();
          this._initTopScrollbarDrag();
          wrap.addEventListener('scroll', () => {
            this._updateCustomTopScrollbar();
          });
        }
      }, 200);

      // Update thumb on window resize
      window.addEventListener('resize', () => {
        this._updateCustomTopScrollbar();
      });

      // Keyboard shortcuts
      document.addEventListener('keydown', (e) => {
        if (e.ctrlKey && e.key === 'z') {
          e.preventDefault();
          if (e.shiftKey) {
            this.redo();
          } else {
            this.undo();
          }
        }
      });
    },

    async loadPreset(presetId) {
      try {
        const response = await fetch(`/api/v1/presets/`);
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

    applyFilter() {
        this._saveState();
        this.loadPreview(1);
    },

    addFilter() {
      if (this.filters.length >= 5) return;
      this.filters.push({ col: '', op: 'contains', query: '', values: [] });
    },

    removeFilter(idx) {
      if (this.filters.length <= 1) return;
      this.filters.splice(idx, 1);
    },

    async fetchColumnValues(idx) {
      const f = this.filters[idx];
      if (!f || !f.col || !this.fileId) return;
      f.values = [];
      try {
        const resp = await fetch(`/api/v1/files/${this.fileId}/column-values/?column=${encodeURIComponent(f.col)}`);
        const data = await resp.json();
        if (resp.ok && data.values) {
          f.values = data.values;
        }
      } catch (e) {
        console.error('DataForge: fetchColumnValues error', e);
      }
    },

    async loadPreview(page = 1, resetSort = true) {
      this.isLoading = true;
      try {
        this.currentPage = page;
        if (resetSort) {
          this.sortColumn = null;
          this.sortOrder = null;
          this.sortVersion = 0;
        }
        let url = `/api/v1/files/${this.fileId}/preview/?page=${page}&page_size=${this.pageSize}`;
        url += this._filterQueryString();
        const response = await fetch(url);
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

              // Apply saved column selections from sessionStorage
              if (this._pendingColumnSelections) {
                this.files[0].metadata.columns.forEach(c => {
                  const saved = this._pendingColumnSelections.find(s => s.name === c.name);
                  if (saved) c.selected = saved.selected;
                });
                this._pendingColumnSelections = null;
                this.updateDisplayColumns();
              }
          } else {
              // Preserve existing column selections while updating from server
              const oldCols = this.files[0]?.metadata.columns || [];
              columns.forEach(c => {
                const old = oldCols.find(x => x.name === c.name);
                if (old) c.selected = old.selected;
              });
              this.files[0].metadata.columns = columns;
          }
          
          this.totalRows = data.row_count;
          this.previewData = data.preview || [];
          this.quality = data.quality || { complete_rows_pct: 100, problematic_cols_count: 0 };
          this.refreshColumnLists();
          this.updateDisplayColumns();
          this._afterRender();
          this._initColumnSortable();
          // Push initial history snapshot after load
          if (this._history.length === 0) {
            this._pushHistory();
          }
        } else {
          Toast.error(data.error || "Gagal memuat preview data");
        }
      } catch (e) {
        console.error(e);
        Toast.error("Kesalahan jaringan saat memuat preview");
      } finally {
        this.isLoading = false;
      }
    },

    async changePage(page) {
        if (page < 1 || page > this.totalPages) return;
        this.currentPage = page;
        // If a sort is active, re-fetch with sort preserved
        if (this.sortColumn && this.sortOrder) {
            await this._fetchSortedPreview();
        } else {
            await this.loadPreview(page);
        }
        // Scroll table to top
        document.querySelector('.q-table-wrap').scrollTop = 0;
    },

    updateDisplayColumns() {
      if (this.files.length > 0) {
        this.displayColumns = this.files[0].metadata.columns
          .filter(c => c.selected)
          .map(c => c.name);
      }
      this._afterRender();
    },

    selectAll() {
      if (this.files.length > 0) {
        this._pushHistory();
        this.files[0].metadata.columns.forEach(c => c.selected = true);
        this.updateDisplayColumns();
        Toast.info('Semua kolom dipilih');
      }
    },
    
    deselectAll() {
      if (this.files.length > 0) {
        this._pushHistory();
        this.files[0].metadata.columns.forEach(c => c.selected = false);
        this.updateDisplayColumns();
        Toast.info('Semua kolom dihapus');
      }
    },

    toggleColumn(fileId, colName, isChecked) {
      this._pushHistory();
      this.updateDisplayColumns();
      this._saveState();
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
        const headers = {'Content-Type': 'application/json'};
        if (this._csrfToken) {
          headers['X-CSRFToken'] = this._csrfToken;
        }
 
        const response = await fetch('/api/v1/export/', {
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
            include_comparison: this.includeComparison,
            export_scope: this.exportScope,
            filters: this.filters.filter(f => f.col && f.query).map(f => ({ col: f.col, op: f.op, query: f.query })),
            filter_logic: this.filterLogic,
            sort_by: this.sortColumn,
            sort_order: this.sortOrder
          })
        });
        
        const data = await response.json();
        
        if (response.ok && data.url) {
          Toast.success(`Ekspor ${format.toUpperCase()} berhasil!`);
          
          try {
            const fileResponse = await fetch(data.url);
            const blob = await fileResponse.blob();
            
            // Use the server-generated timestamped filename
            const suggestedName = data.filename || `Data_Export.${format}`;
            
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
        const response = await fetch('/api/v1/processor/aggregate/', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': this._csrfToken
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
          this._saveState();
          Toast.success("Agregasi berhasil! Hasil ringkasan muncul di panel tepat di atas tabel preview.");
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
      
      const sanitize = v =>
        typeof v === 'string' && /^[=+\-@\t]/.test(v) ? "'" + v : v;

      const headers = this.aggregationColumns.join(',');
      const rows = this.aggregationResult.map(row =>
        this.aggregationColumns.map(col => {
          let val = sanitize(row[col]);
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
        const response = await fetch('/api/v1/processor/compare/', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': this._csrfToken
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
          this._saveState();
          Toast.success(data.message + ' — Hasil tersedia untuk export XLSX.');
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

    async applyDatetime() {
      if (!this.fileId) return;
      if (!this.tools.datetime.dateCol && !this.tools.datetime.timeCol) {
        Toast.info("Mencoba deteksi otomatis kolom tanggal...");
      }

      Toast.info("Menormalisasi waktu...");
      try {
        const response = await fetch('/api/v1/processor/datetime/', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': this._csrfToken
          },
          body: JSON.stringify({
            file_id: this.fileId,
            dateCol: this.tools.datetime.dateCol,
            timeCol: this.tools.datetime.timeCol,
            format: this.tools.datetime.format,
            dropOriginal: this.tools.datetime.dropOriginal
          })
        });

        const data = await response.json();
        if (response.ok) {
          this._saveState();
          Toast.success(data.message);
          this.fileId = data.new_file_id;
          window.history.replaceState({}, '', `/workspace/?file_id=${data.new_file_id}`);
          this.files = [];
          await this.loadPreview();
        } else {
          Toast.error(data.error || "Gagal menormalisasi waktu");
        }
      } catch (e) {
        console.error(e);
        Toast.error("Terjadi kesalahan jaringan.");
      }
    },

    async generateChart() {
      if (!this.tools.chart.xCol || !this.tools.chart.yCol) {
        Toast.warning("Pilih Kolom X dan Kolom Y terlebih dahulu.");
        return;
      }

      Toast.info("Membuat grafik...");

      let chartDataPoints;
      if (this.tools.chart.source === 'agregasi') {
        if (!this.aggregationResult || this.aggregationResult.length === 0) {
          Toast.warning("Data agregasi kosong.");
          return;
        }
        chartDataPoints = this._extractChartData(this.aggregationResult);
      } else {
        try {
          const response = await fetch('/api/v1/processor/chart-data/', {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              'X-CSRFToken': this._csrfToken
            },
            body: JSON.stringify({
              file_id: this.fileId,
              x_col: this.tools.chart.xCol,
              y_col: this.tools.chart.yCol,
              max_points: 1000,
              filters: this.filters.filter(f => f.col && f.query).map(f => ({ col: f.col, op: f.op, query: f.query })),
              filter_logic: this.filterLogic,
            })
          });
          const data = await response.json();
          chartDataPoints = response.ok && data.data ? data.data : this._extractChartData(this.previewData);
        } catch (e) {
          chartDataPoints = this._extractChartData(this.previewData);
        }
      }

      if (!chartDataPoints || chartDataPoints.length === 0) {
        Toast.warning("Data kosong.");
        return;
      }

      this._renderChart(chartDataPoints);
    },

    _extractChartData(dataSource) {
      return dataSource.map(row => ({
        x: (row[this.tools.chart.xCol] == null || row[this.tools.chart.xCol] === '') ? 'N/A' : String(row[this.tools.chart.xCol]),
        y: parseFloat(row[this.tools.chart.yCol]) || 0,
      }));
    },

    _renderChart(chartData) {
      const labels = [], values = [];
      for (const d of chartData) {
        labels.push(d.x);
        values.push(d.y);
      }

      const ctx = document.getElementById('chart-preview').getContext('2d');
      if (this.chartInstance) {
        this.chartInstance.destroy();
      }

      const bgColors = [
        'rgba(16, 185, 129, 0.7)',
        'rgba(59, 130, 246, 0.7)',
        'rgba(245, 158, 11, 0.7)',
        'rgba(239, 68, 68, 0.7)',
        'rgba(139, 92, 246, 0.7)',
        'rgba(6, 182, 212, 0.7)'
      ];

      this.chartInstance = new Chart(ctx, {
        type: this.tools.chart.type,
        data: {
          labels: labels,
          datasets: [{
            label: this.tools.chart.yCol,
            data: values,
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

      setTimeout(() => {
        Toast.success('Grafik telah dibuat.');
      }, 800);
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
        const response = await fetch('/api/v1/presets/', {
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
      if (this._csrfToken) return this._csrfToken;
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
