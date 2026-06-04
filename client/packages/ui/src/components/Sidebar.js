import { t } from '../../../app/src/i18n/index.js';

const esc = (str) => String(str)
    .replace(/&/g, '&amp;')
    .replace(/'/g, '&#39;')
    .replace(/"/g, '&quot;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');

export const SidebarComponent = {
    render(data) {
        const {
            rasters,
            activeLayerIds,
            loadingIds,
            projects,
            activeProject,
            vectorLayers,
            activeVectorLayerId,
            visibleVectorLayerIds,
        } = data;

        return `
            <div class="mb-6">
                <div class="px-4 py-2 flex justify-between items-center mb-1">
                    <h3 class="text-[10px] font-black text-slate-400 uppercase tracking-widest">${t('sidebar.raster.title')}</h3>
                    <button onclick="document.getElementById('raster-upload-input').click()" class="text-indigo-500 hover:text-indigo-700 font-bold text-[10px]">${t('sidebar.raster.import')}</button>
                </div>
                <input type="file" id="raster-upload-input" class="hidden" multiple accept=".tif,.tiff,.jp2,.vrt,.img">
                <div id="raster-list">
                    ${this.renderRasterSection(rasters, activeLayerIds, loadingIds)}
                </div>
            </div>

            <div class="mx-4 border-t border-slate-100 my-4"></div>

            <div class="mb-6">
                <div class="px-4 py-2 flex justify-between items-center mb-1">
                    <h3 class="text-[10px] font-black text-slate-400 uppercase tracking-widest">${t('sidebar.vector.title')}</h3>
                    <button onclick="RS.createProject()" class="text-emerald-500 hover:text-emerald-700 font-bold text-[10px]">${t('sidebar.vector.newProject')}</button>
                </div>
                <div id="vector-list-container">
                    ${this.renderVectorSection(
                        projects,
                        activeProject,
                        vectorLayers,
                        activeVectorLayerId,
                        visibleVectorLayerIds
                    )}
                </div>
            </div>
        `;
    },

    renderRasterSection(rasters, activeIds, loadingIds) {
        if (!rasters || rasters.length === 0) {
            return `
                <div class="flex flex-col items-center justify-center py-20 text-slate-300">
                    <svg class="w-12 h-12 mb-4 opacity-20" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z"></path></svg>
                    <span class="text-xs font-medium italic">${t('sidebar.raster.waiting')}</span>
                </div>
            `;
        }

        const groups = {};
        rasters.forEach((raster) => {
            const bundleId = raster.bundle_id || 'unclassed';
            if (!groups[bundleId]) groups[bundleId] = [];
            groups[bundleId].push(raster);
        });

        return Object.entries(groups).map(([bundleId, items]) => `
            <div class="bg-slate-50 rounded-xl border border-slate-200 overflow-visible mb-4 mx-2 shadow-sm">
                <div class="px-3 py-2 bg-slate-100 border-b border-slate-200 text-[9px] font-black text-slate-500 flex justify-between items-center uppercase tracking-wider">
                    <div class="flex items-center">
                        <span class="w-1.5 h-1.5 rounded-full bg-slate-400 mr-2"></span>
                        ${t('sidebar.raster.bundle', { id: bundleId.substring(0, 8) })}
                    </div>
                    <span class="bg-white px-1.5 py-0.5 rounded border border-slate-300">${t('sidebar.raster.members', { count: items.length })}</span>
                </div>
                <div class="divide-y divide-slate-100 bg-white">
                    ${items.map((raster) => this.renderItem(raster, activeIds.has(raster.id), loadingIds.has(raster.id))).join('')}
                </div>
            </div>
        `).join('');
    },

    renderItem(raster, isActive, isLoading) {
        const checkedAttr = isActive ? 'checked="checked"' : '';
        const activeItemClass = isActive ? 'bg-indigo-50/50 border-indigo-100' : 'border-transparent';
        const activeTextClass = isActive ? 'text-indigo-700' : 'text-slate-700';
        const dragId = esc(raster.id);
        const bundleId = esc(raster.bundle_id ?? 'unclassed');

        return `
            <div class="layer-item p-3 flex items-center hover:bg-slate-50 transition-all group border-l-4 ${activeItemClass} cursor-grab active:cursor-grabbing"
                 draggable="true"
                 data-layer-drag-type="raster"
                 data-layer-drag-id="${dragId}"
                 data-layer-bundle-id="${bundleId}"
                 data-id="${raster.id}">
                <div class="mr-2 shrink-0 text-slate-300 group-hover:text-slate-400" title="Drag to reorder">
                    <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                              d="M8 6h.01M8 12h.01M8 18h.01M16 6h.01M16 12h.01M16 18h.01"/>
                    </svg>
                </div>
                <div class="mr-3 flex items-center justify-center">
                    <div class="relative w-4 h-4">
                        <input type="checkbox"
                             ${checkedAttr}
                             data-id="${raster.id}"
                             class="layer-checkbox w-4 h-4 rounded border-slate-300 text-indigo-600 focus:ring-indigo-500 transition-all cursor-pointer">
                        ${isLoading ? `
                             <div class="absolute inset-0 bg-white/90 flex items-center justify-center rounded-sm">
                              <div class="w-3 h-3 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin"></div>
                            </div>` : ''}
                    </div>
                </div>

                <div class="flex-1 min-w-0 cursor-pointer item-info" data-id="${raster.id}">
                    <div class="text-sm font-bold ${activeTextClass} truncate">
                      ${raster.file_name}
                    </div>
                    <div class="flex items-center space-x-2 mt-1">
                        <span class="text-[9px] font-mono font-medium text-slate-400 bg-slate-100 px-1.5 py-0.5 rounded">
                          ${raster.width} × ${raster.height}
                        </span>
                        <span class="text-[9px] font-bold text-slate-400">B:${raster.bands}</span>
                        ${isActive ? `
                            <span class="flex items-center text-[9px] text-indigo-500 font-black uppercase tracking-tighter">
                                <span class="w-1 h-1 rounded-full bg-indigo-500 animate-pulse mr-1"></span>
                                ${t('sidebar.raster.onMap')}
                            </span>` : ''}
                  </div>
                </div>

                ${this.renderRasterActions(raster)}
            </div>
        `;
    },

    renderRasterActions(raster) {
        const indexId = esc(raster.index_id);
        const rasterId = esc(raster.id);
        const fileName = esc(raster.file_name);
        const actions = [
            {
                label: 'Spectral Profile',
                title: t('sidebar.raster.spectrumTitle'),
                tone: 'violet',
                icon: this.renderActionIcon('spectrum'),
                onclick: `event.stopPropagation(); this.closest('details')?.removeAttribute('open'); RS.showSpectrumMode('${indexId}')`,
            },
            {
                label: 'Raster Statistics',
                title: t('sidebar.raster.statsTitle'),
                tone: 'sky',
                icon: this.renderActionIcon('stats'),
                onclick: `event.stopPropagation(); this.closest('details')?.removeAttribute('open'); RS.openRasterStatistics('${indexId}')`,
            },
            {
                label: 'Resample Raster',
                title: 'Resample raster',
                tone: 'teal',
                icon: this.renderActionIcon('resample'),
                onclick: `event.stopPropagation(); this.closest('details')?.removeAttribute('open'); RS.openResampleModal('${indexId}')`,
            },
            {
                label: 'Radiometric Calibration',
                title: 'Radiometric calibration',
                tone: 'cyan',
                icon: this.renderActionIcon('radiometric'),
                onclick: `event.stopPropagation(); this.closest('details')?.removeAttribute('open'); RS.openPreprocessingModal('radiometric', '${indexId}')`,
            },
            {
                label: 'Geometric Correction',
                title: 'Geometric correction',
                tone: 'cyan',
                icon: this.renderActionIcon('geometric'),
                onclick: `event.stopPropagation(); this.closest('details')?.removeAttribute('open'); RS.openPreprocessingModal('geometric', '${indexId}')`,
            },
            {
                label: 'Supervised Classification',
                title: 'Supervised classification',
                tone: 'emerald',
                icon: this.renderActionIcon('classification'),
                onclick: `event.stopPropagation(); this.closest('details')?.removeAttribute('open'); RS.openClassificationModal('supervised', '${indexId}')`,
            },
            {
                label: 'Unsupervised Classification',
                title: 'Unsupervised classification',
                tone: 'emerald',
                icon: this.renderActionIcon('clusters'),
                onclick: `event.stopPropagation(); this.closest('details')?.removeAttribute('open'); RS.openClassificationModal('unsupervised', '${indexId}')`,
            },
            {
                label: 'Deep Learning Segmentation',
                title: 'Deep learning segmentation',
                tone: 'emerald',
                icon: this.renderActionIcon('segmentation'),
                onclick: `event.stopPropagation(); this.closest('details')?.removeAttribute('open'); RS.openClassificationModal('segmentation', '${indexId}')`,
            },
            {
                label: 'Attribute Table',
                title: t('sidebar.raster.attrTitle'),
                tone: 'indigo',
                icon: this.renderActionIcon('table'),
                onclick: `event.stopPropagation(); this.closest('details')?.removeAttribute('open'); RS.openAttriRaster('${indexId}','${fileName}')`,
            },
            {
                label: 'Remove Raster',
                title: t('sidebar.raster.removeTitle'),
                tone: 'red',
                icon: this.renderActionIcon('delete'),
                className: 'btn-delete',
                dataAttrs: `data-id="${rasterId}"`,
                onclick: `this.closest('details')?.removeAttribute('open')`,
            },
        ];

        return `
            <details class="layer-action-menu relative shrink-0 ml-2 opacity-0 group-hover:opacity-100 focus-within:opacity-100 transition-opacity"
                     ontoggle="RS.positionRasterActionMenu(this)">
                <summary onclick="event.stopPropagation()"
                         class="list-none [&::-webkit-details-marker]:hidden w-7 h-7 flex items-center justify-center rounded-lg text-slate-400 hover:text-indigo-600 hover:bg-indigo-50 cursor-pointer"
                         title="Layer actions">
                    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                              d="M12 6h.01M12 12h.01M12 18h.01"/>
                    </svg>
                </summary>
                <div data-raster-action-panel
                     class="fixed z-[1500] w-64 overflow-hidden rounded-xl border border-slate-200 bg-white shadow-xl">
                    <div class="flex items-center gap-2 border-b border-slate-100 bg-slate-50 px-3 py-2">
                        <div class="flex h-7 w-7 items-center justify-center rounded-lg bg-indigo-600 text-white">
                            <svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                                      d="M4 7h16M4 12h16M4 17h16"/>
                            </svg>
                        </div>
                        <div class="min-w-0">
                            <div class="truncate text-[10px] font-black uppercase tracking-widest text-slate-600">Raster Functions</div>
                            <div class="truncate text-[9px] font-semibold text-slate-400">${fileName}</div>
                        </div>
                    </div>
                    <div class="max-h-72 overflow-y-auto p-1.5">
                        ${actions.map(action => this.renderRasterActionItem(action)).join('')}
                    </div>
                </div>
            </details>
        `;
    },

    renderRasterActionItem(action) {
        const tone = this.rasterActionToneClasses(action.tone);
        const className = action.className ? ` ${action.className}` : '';
        const dataAttrs = action.dataAttrs ? ` ${action.dataAttrs}` : '';

        return `
            <button${dataAttrs}
                    onclick="${action.onclick}"
                    class="group flex w-full items-center gap-3 rounded-lg px-2.5 py-2 text-left text-xs font-bold text-slate-600 transition-colors ${tone.row}${className}"
                    title="${esc(action.title)}">
                <span class="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-slate-100 text-slate-400 transition-colors ${tone.icon}">
                    ${action.icon}
                </span>
                <span class="min-w-0 flex-1 truncate">${action.label}</span>
            </button>
        `;
    },

    rasterActionToneClasses(tone) {
        const classes = {
            violet: {
                row: 'hover:bg-violet-50 hover:text-violet-600',
                icon: 'group-hover:bg-violet-100 group-hover:text-violet-600',
            },
            sky: {
                row: 'hover:bg-sky-50 hover:text-sky-600',
                icon: 'group-hover:bg-sky-100 group-hover:text-sky-600',
            },
            teal: {
                row: 'hover:bg-teal-50 hover:text-teal-600',
                icon: 'group-hover:bg-teal-100 group-hover:text-teal-600',
            },
            cyan: {
                row: 'hover:bg-cyan-50 hover:text-cyan-600',
                icon: 'group-hover:bg-cyan-100 group-hover:text-cyan-600',
            },
            emerald: {
                row: 'hover:bg-emerald-50 hover:text-emerald-600',
                icon: 'group-hover:bg-emerald-100 group-hover:text-emerald-600',
            },
            indigo: {
                row: 'hover:bg-indigo-50 hover:text-indigo-600',
                icon: 'group-hover:bg-indigo-100 group-hover:text-indigo-600',
            },
            red: {
                row: 'hover:bg-red-50 hover:text-red-600',
                icon: 'group-hover:bg-red-100 group-hover:text-red-600',
            },
        };
        return classes[tone] || {
            row: 'hover:bg-slate-50 hover:text-slate-700',
            icon: 'group-hover:bg-slate-200 group-hover:text-slate-700',
        };
    },

    renderActionIcon(name) {
        const icons = {
            spectrum: '<svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6m6 0V9a2 2 0 012-2h2a2 2 0 012 2v10m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14"/></svg>',
            stats: '<svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 19V5m0 14h16M8 17V9m4 8V7m4 10v-5"/></svg>',
            resample: '<svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 7h10m0 0l-3-3m3 3l-3 3M20 17H10m0 0l3-3m-3 3l3 3"/></svg>',
            radiometric: '<svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 19h16M6 17l3-8 4 5 3-9 2 12"/></svg>',
            geometric: '<svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 5h7v7H4zM13 12l7 7m0-7v7h-7"/></svg>',
            classification: '<svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 5h6v6H4zM14 5h6v6h-6zM4 15h6v4H4zM14 15h6v4h-6z"/></svg>',
            clusters: '<svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 8h.01M12 6h.01M17 8h.01M9 14h.01M15 14h.01M12 19h.01"/></svg>',
            segmentation: '<svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 8l4-4 4 4-4 4-4-4zm8 8l4-4 4 4-4 4-4-4z"/></svg>',
            table: '<svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 10h18M3 6h18M3 14h18M3 18h18"/></svg>',
            delete: '<svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862A2 2 0 015.867 19.142L5 7m5 4v6m4-6v6M4 7h16"/></svg>',
        };
        return icons[name] || icons.table;
    },

    renderVectorSection(projects, activeProject, layers, activeLayerId, visibleIds) {
        if (!projects || projects.length === 0) return this.renderEmpty(t('sidebar.vector.emptyProjects'));

        return `
            <div class="mx-2">
                <select onchange="RS.selectProject(this.value)" class="w-full mb-3 p-2 text-xs border border-slate-200 rounded-lg bg-white text-slate-600 focus:ring-2 focus:ring-emerald-500/20 outline-none transition-all">
                    <option value="">${t('sidebar.vector.selectProject')}</option>
                    ${projects.map((project) => `<option value="${project.id}" ${activeProject?.id === project.id ? 'selected' : ''}>${project.name}</option>`).join('')}
                </select>

                ${activeProject ? `
                    <div class="bg-emerald-50/30 rounded-xl border border-emerald-100 overflow-hidden shadow-sm">
                        <div class="px-3 py-2 bg-emerald-100/50 border-b border-emerald-100 flex justify-between items-center">
                            <span class="text-[9px] font-black text-emerald-700 uppercase tracking-wider">📂 ${t('sidebar.vector.projectTag', { name: activeProject.name })}</span>
                            <div class="flex items-center gap-1">
                                <button onclick="event.stopPropagation();
                                                 document.getElementById('shapefile-upload-input').dataset.layerId='${activeProject.id}';
                                                 document.getElementById('shapefile-upload-input').click()"
                                        class="w-5 h-5 flex items-center justify-center bg-white rounded border border-amber-200 text-amber-500 hover:bg-amber-50 transition-colors"
                                        title="${t('sidebar.vector.importTitle')}">
                                    <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                                              d="M9 13h6m-3-3v6m5 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586
                                                 a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/>
                                    </svg>
                                </button>
                                <button onclick="RS.createLayer()"
                                        class="w-5 h-5 flex items-center justify-center bg-white rounded border border-emerald-200 text-emerald-600 hover:bg-emerald-50 transition-colors"
                                        title="${t('sidebar.vector.newLayerTitle')}">＋</button>
                            </div>
                        </div>
                        <div class="divide-y divide-emerald-50 bg-white" id="vector-list">
                            ${layers.length === 0
                                ? `<div class="p-6 text-center text-[10px] text-slate-400 italic">${t('sidebar.vector.emptyLayers')}</div>`
                                : layers.map((layer) => this.renderVectorItem(
                                    layer,
                                    activeLayerId === layer.id,
                                    visibleIds?.has(layer.id),
                                    activeProject?.id
                                )).join('')}
                        </div>
                    </div>
                ` : `<div class="text-center py-6 text-[10px] text-slate-300 italic">${t('sidebar.vector.selectHint')}</div>`}
            </div>
        `;
    },

    renderVectorItem(layer, isActive, isVisible, activeProjectId = null) {
        const rowClass = isActive
            ? 'border-l-4 border-emerald-500 bg-emerald-50/20'
            : 'border-l-4 border-transparent';
        const nameClass = isActive ? 'text-emerald-700' : 'text-slate-700';
        const dragId = esc(layer.id);
        const projectId = esc(layer.project_id ?? layer.projectId ?? activeProjectId ?? '');

        return `
            <div class="p-3 flex items-center hover:bg-emerald-50/50 transition-all group ${rowClass} cursor-grab active:cursor-grabbing"
                 draggable="true"
                 data-layer-drag-type="vector"
                 data-layer-drag-id="${dragId}"
                 data-layer-project-id="${projectId}"
                 data-vector-id="${layer.id}">
                <div class="mr-2 shrink-0 text-slate-300 group-hover:text-emerald-400" title="Drag to reorder">
                    <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                              d="M8 6h.01M8 12h.01M8 18h.01M16 6h.01M16 12h.01M16 18h.01"/>
                    </svg>
                </div>
                <div class="mr-3 shrink-0">
                    <input type="checkbox"
                           ${isVisible ? 'checked' : ''}
                           onclick="event.stopPropagation(); RS.toggleVectorVisibility('${layer.id}')"
                           class="vector-layer-checkbox w-4 h-4 rounded border-emerald-300 text-emerald-600 focus:ring-emerald-500 cursor-pointer">
                </div>

                <div class="flex-1 min-w-0 cursor-pointer" onclick="RS.setActiveVectorLayer('${layer.id}')">
                    <div class="text-sm font-bold ${nameClass} truncate">${layer.name}</div>
                    <div class="text-[9px] text-slate-400 mt-0.5 tracking-tight font-mono">
                        ${isActive
                            ? `<span class="text-emerald-600 font-bold">${t('sidebar.vector.currentEditing')}</span>`
                            : t('sidebar.vector.clickToActivate')}
                    </div>
                </div>

                <div class="flex items-center gap-0.5 opacity-0 group-hover:opacity-100 transition-opacity shrink-0">
                    <button onclick="event.stopPropagation(); RS.openAttriVector('${layer.id}', '${esc(layer.name)}')"
                            class="p-1.5 text-slate-300 hover:text-indigo-500 hover:bg-indigo-50 rounded-lg transition-colors"
                            title="${t('sidebar.vector.attrTitle')}">
                        <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                                  d="M3 10h18M3 6h18M3 14h18M3 18h18"/>
                        </svg>
                    </button>

                    <button onclick="event.stopPropagation(); RS.deleteLayer('${layer.id}')"
                            class="p-1.5 text-slate-300 hover:text-red-500 hover:bg-red-50 rounded-lg transition-colors"
                            title="${t('sidebar.vector.deleteTitle')}">
                        <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                                  d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/>
                        </svg>
                    </button>
                </div>
            </div>
        `;
    },

    renderEmpty(text) {
        return `<div class="text-center py-10 text-[10px] text-slate-300 italic tracking-widest uppercase">${text}</div>`;
    }
};
