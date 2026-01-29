// Question Bank Application JavaScript
// Extracted from index.html for maintainability

// State
        let editor = null;
        let courses = [];
        let banks = [];
        let editingQuestionId = null;
        let selectedQuestions = new Set();
        let bulkSelectedQuestions = new Set(); // For bulk operations in question list
        let bulkMode = false;
        let questionOverrides = {}; // Per-question spacing overrides for exam builder
        let currentExamQuestions = []; // Stores current exam preview questions with points
        let cachedSectionQuestions = {}; // Cache questions per section to avoid re-randomizing
        let cachedFinalQuestions = null; // Cache final question list after all filtering
        let hasCachedQuestions = false; // Simple flag - reset when template changes
        let isRestoringState = false; // Flag to prevent saving during restore

        // Toast notifications
        function showToast(message, type = 'info') {
            // Remove existing toasts
            document.querySelectorAll('.toast-notification').forEach(t => t.remove());

            const colors = {
                success: 'bg-emerald-500',
                error: 'bg-red-500',
                warning: 'bg-amber-500',
                info: 'bg-sky-500'
            };

            const toast = document.createElement('div');
            toast.className = `toast-notification fixed bottom-4 right-4 ${colors[type] || colors.info} text-white px-4 py-3 rounded-lg shadow-lg z-50 transition-opacity duration-300`;
            toast.textContent = message;
            document.body.appendChild(toast);

            // Auto-remove after 3 seconds
            setTimeout(() => {
                toast.style.opacity = '0';
                setTimeout(() => toast.remove(), 300);
            }, 3000);
        }

        // Dark mode - check saved preference or system preference
        function initDarkMode() {
            const saved = localStorage.getItem('darkMode');
            const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
            if (saved === 'true' || (saved === null && prefersDark)) {
                document.documentElement.classList.add('dark');
            } else {
                document.documentElement.classList.remove('dark');
            }
        }

        function toggleDarkMode() {
            const isDark = document.documentElement.classList.toggle('dark');
            localStorage.setItem('darkMode', isDark);
            // Update Monaco editor theme
            if (editor) {
                monaco.editor.setTheme(isDark ? 'vs-dark' : 'vs');
            }
            lucide.createIcons();
        }

        // Initialize - fast startup, load data in background
        document.addEventListener('DOMContentLoaded', async () => {
            console.log('[DEBUG] DOMContentLoaded started - app.js loaded');
            initDarkMode();
            lucide.createIcons();
            setupEventListeners();
            // Load data - courses must complete first for dropdowns
            console.log('[DEBUG] Loading courses...');
            await loadCourses();
            console.log('[DEBUG] Courses loaded, loading tags...');
            loadTags();
            // Don't load all questions at startup - wait for course selection
            showSelectCoursePrompt();
            // Load trash count for sidebar badge
            updateTrashCount();
            // Load usage stats for sidebar
            loadUsageStats();
            // Restore previous view state
            restoreViewState();
            console.log('[DEBUG] DOMContentLoaded complete');
        });

        // Save/restore view state for page refresh persistence
        function saveViewState() {
            if (isRestoringState) return; // Don't save while restoring
            const state = {
                currentView: document.querySelector('.view:not(.hidden)')?.id?.replace('view-', '') || 'questions',
                currentTemplateId: currentTemplateId,
                templateCourseFilter: document.getElementById('template-course-selector')?.value,
                examSections: examSections,
                questionOverrides: questionOverrides,
                sectionIdCounter: sectionIdCounter,
                examTitle: document.getElementById('exam-title')?.value,
                examCourse: document.getElementById('exam-course')?.value,
                examInstructor: document.getElementById('exam-instructor')?.value,
                examTerm: document.getElementById('exam-term')?.value,
                examInstructions: document.getElementById('exam-instructions')?.value,
                examLineLength: document.getElementById('exam-line-length')?.value,
                examSolutionSpace: document.getElementById('exam-solution-space')?.value,
                examQuizMode: document.getElementById('exam-quiz-mode')?.checked,
                examIncludeId: document.getElementById('exam-include-id')?.checked,
                examSplitMc: document.getElementById('exam-split-mc')?.checked,
                examAnswers: document.getElementById('exam-answers')?.checked,
            };
            localStorage.setItem('examBuilderState', JSON.stringify(state));
        }

        function restoreViewState() {
            const saved = localStorage.getItem('examBuilderState');
            if (!saved) return;

            try {
                const state = JSON.parse(saved);

                // Restore view after a short delay to let DOM initialize
                setTimeout(async () => {
                    isRestoringState = true; // Prevent saving during restore

                    // Restore exam builder state variables first
                    if (state.examSections) examSections = state.examSections;
                    if (state.questionOverrides) questionOverrides = state.questionOverrides;
                    if (state.sectionIdCounter) sectionIdCounter = state.sectionIdCounter;
                    if (state.currentTemplateId) currentTemplateId = state.currentTemplateId;

                    if (state.currentView && state.currentView !== 'questions') {
                        showView(state.currentView, null);
                    }

                    // Restore form fields
                    if (state.examTitle) document.getElementById('exam-title').value = state.examTitle;
                    if (state.examCourse) document.getElementById('exam-course').value = state.examCourse;
                    if (state.examInstructor) document.getElementById('exam-instructor').value = state.examInstructor;
                    if (state.examTerm) document.getElementById('exam-term').value = state.examTerm;
                    if (state.examInstructions) document.getElementById('exam-instructions').value = state.examInstructions;
                    if (state.examLineLength) document.getElementById('exam-line-length').value = state.examLineLength;
                    if (state.examSolutionSpace) document.getElementById('exam-solution-space').value = state.examSolutionSpace;
                    if (state.examQuizMode !== undefined) document.getElementById('exam-quiz-mode').checked = state.examQuizMode;
                    if (state.examIncludeId !== undefined) document.getElementById('exam-include-id').checked = state.examIncludeId;
                    if (state.examSplitMc !== undefined) document.getElementById('exam-split-mc').checked = state.examSplitMc;
                    if (state.examAnswers !== undefined) document.getElementById('exam-answers').checked = state.examAnswers;

                    // Re-render sections and preview if on exam view
                    if (state.currentView === 'exams') {
                        // Wait for templates to load, then set selector
                        await loadExamTemplates('');

                        // Restore course filter first
                        const courseSelector = document.getElementById('template-course-selector');
                        if (state.templateCourseFilter && courseSelector) {
                            courseSelector.value = state.templateCourseFilter;
                            filterTemplatesByCourse(state.templateCourseFilter);
                        }

                        // Then restore template selection (convert to string for comparison)
                        const templateSelector = document.getElementById('template-selector');
                        if (state.currentTemplateId && templateSelector) {
                            const templateIdStr = String(state.currentTemplateId);
                            templateSelector.value = templateIdStr;
                            // Verify the selection was successful
                            if (templateSelector.value === templateIdStr) {
                                // Load the full template to restore all settings including include_answers and versions
                                await loadExamTemplate(templateIdStr);
                            } else {
                                console.warn('Could not restore template selection:', templateIdStr, 'Options:', Array.from(templateSelector.options).map(o => o.value));
                            }
                        } else if (examSections.length > 0) {
                            // Only render manually if no template to load
                            renderExamSections();
                            await refreshExamPreview();
                        }
                    }

                    isRestoringState = false; // Allow saving again
                }, 100);
            } catch (e) {
                console.error('Error restoring view state:', e);
                isRestoringState = false;
            }
        }

        // Monaco state
        let monacoLoaded = false;
        let monacoLoading = false;
        let pendingEditorValue = '';

        function loadMonaco() {
            return new Promise((resolve) => {
                if (monacoLoaded) { resolve(); return; }
                if (monacoLoading) {
                    // Wait for existing load
                    const check = setInterval(() => {
                        if (monacoLoaded) { clearInterval(check); resolve(); }
                    }, 50);
                    return;
                }
                monacoLoading = true;
                const script = document.createElement('script');
                script.src = 'https://cdnjs.cloudflare.com/ajax/libs/monaco-editor/0.45.0/min/vs/loader.min.js';
                script.onload = () => {
                    const isDark = document.documentElement.classList.contains('dark');
                    require.config({ paths: { vs: 'https://cdnjs.cloudflare.com/ajax/libs/monaco-editor/0.45.0/min/vs' } });
                    require(['vs/editor/editor.main'], function() {
                        editor = monaco.editor.create(document.getElementById('editor-container'), {
                            value: pendingEditorValue,
                            language: 'markdown',
                            theme: isDark ? 'vs-dark' : 'vs',
                            minimap: { enabled: false },
                            lineNumbers: 'off',
                            wordWrap: 'on',
                            fontSize: 14,
                            padding: { top: 12, bottom: 12 },
                            automaticLayout: true,
                            scrollBeyondLastLine: false,
                        });
                        monacoLoaded = true;
                        resolve();
                    });
                };
                document.head.appendChild(script);
            });
        }

        function setupEventListeners() {
            document.getElementById('search-input')?.addEventListener('input', debounce(() => loadQuestions(), 300));
            ['filter-type', 'filter-difficulty'].forEach(id => {
                document.getElementById(id)?.addEventListener('change', () => loadQuestions());
            });
            document.getElementById('filter-course')?.addEventListener('change', () => {
                loadTagsForCourse();
                loadQuestions();
            });
            ['exam-filter-course', 'exam-filter-type', 'exam-filter-week'].forEach(id => {
                document.getElementById(id)?.addEventListener('change', () => loadExamQuestions());
            });
        }

        // Load weeks for a specific filter dropdown
        async function loadWeeksForFilter(weekSelectId) {
            const weekSelect = document.getElementById(weekSelectId);
            if (!weekSelect) return;

            // Get the corresponding course select
            const courseSelectId = weekSelectId === 'filter-week' ? 'filter-course' : 'exam-filter-course';
            const courseCode = document.getElementById(courseSelectId)?.value;

            // Reset the week dropdown
            weekSelect.innerHTML = '<option value="">All Weeks</option>';

            if (!courseCode) return;

            // Fetch weeks for the selected course
            const data = await api(`weeks/?course=${courseCode}`);
            const weeks = data.results || data || [];

            if (weeks.length > 0) {
                weeks.forEach(w => {
                    const displayName = w.name || `Week ${w.number}`;
                    weekSelect.innerHTML += `<option value="${w.id}">${displayName} (${w.question_count || 0})</option>`;
                });
            }

            // Trigger the filter change
            if (weekSelectId === 'filter-week') {
                loadQuestions();
            } else {
                loadExamQuestions();
            }
        }

        // Navigation
        function showView(view, event) {
            event?.preventDefault();
            document.querySelectorAll('.view').forEach(v => v.classList.add('hidden'));
            document.getElementById(`view-${view}`).classList.remove('hidden');
            document.querySelectorAll('.sidebar-item').forEach(l => l.classList.remove('active'));
            // Find and activate the correct sidebar item
            if (event?.target) {
                event.target.closest('.sidebar-item')?.classList.add('active');
            } else {
                // Programmatic navigation - find by view name
                document.querySelectorAll('.sidebar-item').forEach(item => {
                    if (item.getAttribute('onclick')?.includes(`'${view}'`)) {
                        item.classList.add('active');
                    }
                });
            }
            lucide.createIcons();
            if (view === 'exams') {
                loadExamQuestions();
                loadExamTemplates('');
            }
            if (view === 'quizzes') {
                loadQuizSessions();
            }
            if (view === 'trash') {
                loadTrash();
            }
            if (view === 'generate') {
                loadAiBankSelector();
            }
            saveViewState();
        }

        // Get CSRF token from cookies
        function getCookie(name) {
            let cookieValue = null;
            if (document.cookie && document.cookie !== '') {
                const cookies = document.cookie.split(';');
                for (let i = 0; i < cookies.length; i++) {
                    const cookie = cookies[i].trim();
                    if (cookie.substring(0, name.length + 1) === (name + '=')) {
                        cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                        break;
                    }
                }
            }
            return cookieValue;
        }

        // API
        async function api(endpoint, method = 'GET', data = null) {
            console.log('[DEBUG] api() called:', endpoint, method);
            const headers = { 'Content-Type': 'application/json' };

            // Include CSRF token for state-changing requests
            if (method !== 'GET' && method !== 'HEAD') {
                const csrfToken = getCookie('csrftoken');
                if (csrfToken) {
                    headers['X-CSRFToken'] = csrfToken;
                }
            }

            const options = {
                method,
                headers,
                credentials: 'same-origin'  // Include session cookies
            };
            if (data) options.body = JSON.stringify(data);
            const res = await fetch(`/api/${endpoint}`, options);
            console.log('[DEBUG] api() response status:', res.status, res.ok);
            if (!res.ok) {
                if (res.status === 403) {
                    // Try to parse the response to check if it's a permission error or auth failure
                    try {
                        const errorJson = await res.json();
                        if (errorJson.error) {
                            // This is a permission error from the view, show it to user
                            console.log('[DEBUG] 403 - permission error:', errorJson.error);
                            alert('Permission denied: ' + errorJson.error);
                            return {};
                        }
                    } catch (e) {
                        // JSON parse failed, assume it's an auth redirect
                    }
                    // Session expired, redirect to login
                    console.log('[DEBUG] 403 - redirecting to login');
                    window.location.href = '/login/';
                    return {};
                }
                console.log('[DEBUG] api() non-OK response:', res.status);
            }
            if (method === 'DELETE') return {};
            const json = await res.json();
            console.log('[DEBUG] api() returning data for', endpoint);
            return json;
        }

        // Data Loading
        async function loadCourses() {
            const data = await api('courses/');
            courses = data.results || data || [];
            document.getElementById('stat-courses').textContent = courses.length;
            renderCourses();
            updateCourseFilters();
            await loadBanks();
        }

        async function loadBanks() {
            const data = await api('banks/');
            banks = data.results || data || [];
            updateBankSelect();
        }

        let allTags = [];
        let selectedTags = [];

        async function loadTags() {
            const data = await api('tags/');
            allTags = data.results || data || [];
            renderTagCheckboxes();
        }

        async function loadTagsForCourse() {
            const course = document.getElementById('filter-course')?.value;
            selectedTags = []; // Reset selected tags when course changes
            updateTagButtonText();

            if (!course) {
                // No course selected, show all tags
                const data = await api('tags/');
                allTags = data.results || data || [];
            } else {
                // Get tags for this course
                const data = await api(`tags/?course=${course}`);
                allTags = data.results || data || [];
            }
            renderTagCheckboxes();
        }

        function renderTagCheckboxes() {
            const container = document.getElementById('tag-checkboxes');
            if (!container) return;
            container.innerHTML = allTags.map(t => `
                <label class="flex items-center gap-2 px-2 py-1.5 rounded-lg hover:bg-gray-100 dark:hover:bg-slate-700 cursor-pointer">
                    <input type="checkbox" value="${escapeHtml(t.name)}" onchange="onTagCheckChange()"
                        class="w-4 h-4 rounded text-sky-500" ${selectedTags.includes(t.name) ? 'checked' : ''}>
                    <span class="text-sm text-gray-700 dark:text-slate-300">${escapeHtml(t.name)}</span>
                </label>
            `).join('');
        }

        function toggleTagDropdown() {
            const dropdown = document.getElementById('tag-dropdown');
            dropdown.classList.toggle('hidden');
        }

        function onTagCheckChange() {
            const checkboxes = document.querySelectorAll('#tag-checkboxes input[type="checkbox"]:checked');
            selectedTags = Array.from(checkboxes).map(cb => cb.value);
            updateTagButtonText();
            loadQuestions();
        }

        function updateTagButtonText() {
            const text = document.getElementById('tag-dropdown-text');
            if (selectedTags.length === 0) {
                text.textContent = 'All Tags';
            } else if (selectedTags.length === 1) {
                text.textContent = selectedTags[0];
            } else {
                text.textContent = `${selectedTags.length} tags`;
            }
        }

        // Close dropdown when clicking outside
        document.addEventListener('click', (e) => {
            const dropdown = document.getElementById('tag-dropdown');
            const btn = document.getElementById('tag-dropdown-btn');
            if (dropdown && btn && !dropdown.contains(e.target) && !btn.contains(e.target)) {
                dropdown.classList.add('hidden');
            }
        });

        let currentPage = 1;
        let totalQuestions = 0;

        async function loadQuestions(page = 1) {
            console.log('[DEBUG] loadQuestions called, page:', page);
            currentPage = page;
            const params = new URLSearchParams();
            const search = document.getElementById('search-input')?.value;
            const course = document.getElementById('filter-course')?.value;
            const type = document.getElementById('filter-type')?.value;
            const difficulty = document.getElementById('filter-difficulty')?.value;

            // Don't load all questions if no course is selected (unless searching)
            if (!course && !search) {
                showSelectCoursePrompt();
                return;
            }

            if (search) params.append('search', search);
            if (course) params.append('course', course);
            selectedTags.forEach(tag => params.append('tags', tag));
            if (type) params.append('type', type);
            if (difficulty) params.append('difficulty', difficulty);
            params.append('page', page);

            console.log('[DEBUG] Fetching questions with params:', params.toString());
            const data = await api(`questions/?${params.toString()}`);
            console.log('[DEBUG] API response:', data);
            console.log('[DEBUG] data.results:', data?.results);
            console.log('[DEBUG] data.count:', data?.count);
            const questions = data.results || data || [];
            console.log('[DEBUG] questions array length:', questions.length);
            totalQuestions = data.count || questions.length;
            const totalPages = Math.ceil(totalQuestions / 50);
            document.getElementById('stat-questions').textContent = totalQuestions;
            document.getElementById('nav-count').textContent = totalQuestions;
            renderQuestions(questions, totalPages);
        }

        async function loadExamQuestions() {
            const params = new URLSearchParams();
            const course = document.getElementById('exam-filter-course')?.value;
            const week = document.getElementById('exam-filter-week')?.value;
            const type = document.getElementById('exam-filter-type')?.value;
            if (course) params.append('course', course);
            if (week) params.append('week', week);
            if (type) params.append('type', type);

            const data = await api(`questions/?${params.toString()}`);
            renderExamQuestions(data.results || data || []);
        }

        // Show prompt to select a course before loading questions
        function showSelectCoursePrompt() {
            const container = document.getElementById('questions-list');
            if (!container) return;
            container.innerHTML = `<div class="p-12 text-center text-gray-400 dark:text-slate-500">
                <i data-lucide="folder-open" class="w-12 h-12 mx-auto mb-3 opacity-50"></i>
                <p class="font-medium">Select a course to view questions</p>
                <p class="text-sm mt-1">Use the Course filter above to narrow down your questions</p>
            </div>`;
            lucide.createIcons();
            document.getElementById('stat-questions').textContent = '-';
            document.getElementById('nav-count').textContent = '-';
        }

        // Renderers
        function renderQuestions(questions, totalPages = 1) {
            const container = document.getElementById('questions-list');
            if (!questions.length) {
                container.innerHTML = `<div class="p-12 text-center text-gray-400 dark:text-slate-500">
                    <i data-lucide="inbox" class="w-12 h-12 mx-auto mb-3 opacity-50"></i>
                    <p class="font-medium">No questions found</p>
                    <p class="text-sm mt-1">Try adjusting your filters or create a new question</p>
                </div>`;
                lucide.createIcons();
                return;
            }

            const questionsList = questions.map(q => {
                const hasMultipleVariants = q.block_types && q.block_types.length > 1;
                const blockVariantsJson = q.block_types ? escapeHtml(JSON.stringify(q.block_types)) : '';
                const tagsHtml = (q.tags || []).map(t => `<span class="inline-block px-1.5 py-0.5 text-xs rounded bg-emerald-100 dark:bg-emerald-900/50 text-emerald-700 dark:text-emerald-300">${escapeHtml(t.name)}</span>`).join(' ');
                return `
                <div class="question-row flex items-start gap-4 p-4 hover:bg-gray-50 dark:hover:bg-slate-700/50 border-b border-gray-100 dark:border-slate-700 last:border-0 group"
                    data-original-text="${escapeHtml(q.text)}"
                    data-original-points="${parseInt(q.points)}"
                    ${blockVariantsJson ? `data-block-variants="${blockVariantsJson}"` : ''}>
                    ${bulkMode ? `<input type="checkbox" class="bulk-checkbox mt-1 w-4 h-4 rounded text-sky-600" data-id="${q.id}" ${bulkSelectedQuestions.has(q.id) ? 'checked' : ''} onclick="event.stopPropagation(); toggleBulkQuestion(${q.id}, this)">` : ''}
                    <div class="flex-1 min-w-0 cursor-pointer" onclick="editQuestion(${q.id})">
                        <div class="flex items-center gap-2 mb-1 flex-wrap">
                            ${q.block_types ? q.block_types.map((v, i) => `<span class="badge ${getTypeBadgeClass(v.type)} ${hasMultipleVariants ? 'cursor-pointer hover:ring-2 hover:ring-offset-1 hover:ring-sky-400' : ''}" ${hasMultipleVariants ? `onmouseenter="previewBlockVariant(event, ${i})" onmouseleave="resetBlockPreview(event)" onclick="event.stopPropagation(); previewBlockVariant(event, ${i})"` : ''}>${formatType(v.type)}</span>`).join('') : `<span class="badge ${getTypeBadgeClass(q.question_type)}">${formatType(q.question_type)}</span>`}
                            <span class="badge ${getDifficultyClass(q.difficulty)}">${q.difficulty || 'medium'}</span>
                            ${q.bank_name ? `<span class="badge bg-purple-100 dark:bg-purple-900/50 text-purple-700 dark:text-purple-300 flex items-center gap-1" title="Bank: ${escapeHtml(q.bank_name)}"><i data-lucide="folder" class="w-3 h-3"></i>${escapeHtml(q.bank_name)}</span>` : ''}
                            ${q.block_name ? `<span class="badge bg-orange-100 dark:bg-orange-900/50 text-orange-700 dark:text-orange-300 flex items-center gap-1" title="Block: ${escapeHtml(q.block_name)} (${q.block_variant_count} variants, pick ${q.block_max_questions})"><i data-lucide="layers" class="w-3 h-3"></i>${q.block_variant_count}v</span>` : ''}
                            ${q.linked_count > 1 ? `<span class="badge bg-indigo-100 dark:bg-indigo-900/50 text-indigo-700 dark:text-indigo-300 flex items-center gap-1"><i data-lucide="link" class="w-3 h-3"></i>${q.linked_count}</span>` : ''}
                            ${q.canonical ? `<span class="badge bg-gray-100 dark:bg-slate-700 text-gray-500 dark:text-slate-400 text-xs">copy</span>` : ''}
                            <span class="text-xs text-gray-400 dark:text-slate-500">${q.course_code || ''}</span>
                        </div>
                        <div class="question-text text-gray-800 dark:text-slate-200 text-sm line-clamp-3">${simpleMarkdown(q.text)}</div>
                        ${tagsHtml ? `<div class="flex flex-wrap gap-1 mt-1">${tagsHtml}</div>` : ''}
                    </div>
                    <div class="text-right flex-shrink-0 flex flex-col items-end gap-2">
                        <div class="flex items-center gap-3">
                            ${q.times_used > 0 ? `<div class="text-center" title="Used ${q.times_used} time${q.times_used > 1 ? 's' : ''}${q.last_used ? ' (last: ' + new Date(q.last_used).toLocaleDateString() + ')' : ''}">
                                <div class="text-sm font-medium ${q.times_used > 5 ? 'text-amber-600 dark:text-amber-400' : 'text-gray-500 dark:text-slate-400'}">${q.times_used}</div>
                                <div class="text-xs text-gray-400 dark:text-slate-500">uses</div>
                            </div>` : ''}
                            <div>
                                <div class="question-points text-lg font-semibold text-gray-900 dark:text-white">${parseInt(q.points)}</div>
                                <div class="text-xs text-gray-400 dark:text-slate-500">pts</div>
                            </div>
                        </div>
                        <div class="opacity-0 group-hover:opacity-100 transition-opacity flex gap-1">
                            <button onclick="event.stopPropagation(); duplicateQuestion(${q.id})" class="p-1.5 rounded-lg hover:bg-gray-200 dark:hover:bg-slate-600" title="Duplicate">
                                <i data-lucide="copy" class="w-4 h-4 text-gray-500 dark:text-slate-400"></i>
                            </button>
                        </div>
                    </div>
                </div>
            `}).join('');

            // Add pagination controls
            let paginationHtml = '';
            if (totalPages > 1) {
                const pageNumbers = [];
                for (let i = 1; i <= Math.min(totalPages, 10); i++) {
                    pageNumbers.push(i);
                }
                paginationHtml = `
                    <div class="flex items-center justify-center gap-2 p-4 border-t border-gray-100 dark:border-slate-700">
                        <button onclick="loadQuestions(${currentPage - 1})" ${currentPage === 1 ? 'disabled' : ''}
                            class="px-3 py-1.5 rounded-lg text-sm ${currentPage === 1 ? 'text-gray-300 dark:text-slate-600 cursor-not-allowed' : 'text-gray-600 dark:text-slate-300 hover:bg-gray-100 dark:hover:bg-slate-700'}">
                            <i data-lucide="chevron-left" class="w-4 h-4"></i>
                        </button>
                        ${pageNumbers.map(p => `
                            <button onclick="loadQuestions(${p})"
                                class="px-3 py-1.5 rounded-lg text-sm ${p === currentPage ? 'bg-sky-100 dark:bg-sky-900/50 text-sky-700 dark:text-sky-300 font-medium' : 'text-gray-600 dark:text-slate-300 hover:bg-gray-100 dark:hover:bg-slate-700'}">
                                ${p}
                            </button>
                        `).join('')}
                        ${totalPages > 10 ? `<span class="text-gray-400 dark:text-slate-500">...</span><span class="text-sm text-gray-500 dark:text-slate-400">${totalPages}</span>` : ''}
                        <button onclick="loadQuestions(${currentPage + 1})" ${currentPage === totalPages ? 'disabled' : ''}
                            class="px-3 py-1.5 rounded-lg text-sm ${currentPage === totalPages ? 'text-gray-300 dark:text-slate-600 cursor-not-allowed' : 'text-gray-600 dark:text-slate-300 hover:bg-gray-100 dark:hover:bg-slate-700'}">
                            <i data-lucide="chevron-right" class="w-4 h-4"></i>
                        </button>
                    </div>
                `;
            }

            container.innerHTML = questionsList + paginationHtml;
            lucide.createIcons();
        }

        function renderCourses() {
            const container = document.getElementById('courses-list');
            if (!courses.length) {
                container.innerHTML = `<div class="col-span-full text-center py-12 text-gray-400 dark:text-slate-500">
                    <p>No courses yet. Create one to get started.</p>
                </div>`;
                return;
            }
            container.innerHTML = courses.map(c => {
                const isOwner = c.is_owner;
                const isShared = c.is_shared;
                const ownerBadge = isOwner
                    ? `<span class="badge bg-emerald-100 dark:bg-emerald-900/50 text-emerald-700 dark:text-emerald-300 text-xs">Owner</span>`
                    : isShared
                        ? `<span class="badge bg-purple-100 dark:bg-purple-900/50 text-purple-700 dark:text-purple-300 text-xs">Shared by ${escapeHtml(c.owner_username || 'unknown')}</span>`
                        : '';
                const shareBtn = isOwner
                    ? `<button onclick="event.stopPropagation(); openShareModal('course', '${c.code}')" class="p-1.5 rounded-lg hover:bg-sky-100 dark:hover:bg-sky-900/50 text-gray-400 hover:text-sky-600" title="Share course">
                        <i data-lucide="share-2" class="w-4 h-4"></i>
                    </button>`
                    : '';
                return `
                <div class="card p-6 cursor-pointer group" onclick="filterByCourse('${c.code}')">
                    <div class="flex items-center justify-between mb-3">
                        <div class="flex items-center gap-2">
                            <span class="badge bg-sky-100 dark:bg-sky-900/50 text-sky-700 dark:text-sky-300">${c.code}</span>
                            ${ownerBadge}
                        </div>
                        <div class="flex items-center gap-1">
                            ${shareBtn}
                            <span class="text-2xl font-bold text-gray-900 dark:text-white">${c.question_count || 0}</span>
                        </div>
                    </div>
                    <h3 class="font-semibold text-gray-900 dark:text-white mb-1">${escapeHtml(c.name)}</h3>
                    <p class="text-sm text-gray-500 dark:text-slate-400 line-clamp-2">${escapeHtml(c.description || 'No description')}</p>
                </div>
            `}).join('');
            lucide.createIcons();
        }

        function renderExamQuestions(questions) {
            const container = document.getElementById('exam-questions-list');
            if (!container) {
                // Exam builder now uses section-based approach, this function is not used
                return;
            }
            container.innerHTML = questions.map(q => {
                const hasMultipleVariants = q.block_types && q.block_types.length > 1;
                const blockVariantsJson = q.block_types ? escapeHtml(JSON.stringify(q.block_types)) : '';
                return `
                <label class="exam-question-row flex items-start gap-3 p-3 rounded-lg hover:bg-gray-50 dark:hover:bg-slate-700/50 cursor-pointer transition-colors ${selectedQuestions.has(q.id) ? 'bg-sky-50 dark:bg-sky-900/30 ring-1 ring-sky-200 dark:ring-sky-700' : ''}"
                    data-question-id="${q.id}"
                    data-original-text="${escapeHtml(q.text)}"
                    data-original-points="${parseInt(q.points)}"
                    ${blockVariantsJson ? `data-block-variants="${blockVariantsJson}"` : ''}>
                    <input type="checkbox" class="mt-1 w-4 h-4 rounded text-sky-600" ${selectedQuestions.has(q.id) ? 'checked' : ''} onchange="toggleQuestion(${q.id}, ${q.points}, this.checked)">
                    <div class="flex-1 min-w-0">
                        <div class="flex items-center gap-2 mb-1 flex-wrap">
                            ${q.block_types ? q.block_types.map((v, i) => `<span class="badge ${getTypeBadgeClass(v.type)} text-xs ${hasMultipleVariants ? 'cursor-pointer hover:ring-2 hover:ring-offset-1 hover:ring-sky-400' : ''}" ${hasMultipleVariants ? `onmouseenter="previewExamBlockVariant(event, ${i})" onmouseleave="resetExamBlockPreview(event)"` : ''}>${formatType(v.type)}</span>`).join('') : `<span class="badge ${getTypeBadgeClass(q.question_type)} text-xs">${formatType(q.question_type)}</span>`}
                            ${q.block_name ? `<span class="badge bg-orange-100 dark:bg-orange-900/50 text-orange-700 dark:text-orange-300 text-xs flex items-center gap-1" title="Block: ${escapeHtml(q.block_name)} (${q.block_variant_count} variants)"><i data-lucide="layers" class="w-3 h-3"></i>${q.block_variant_count}v</span>` : ''}
                            <span class="exam-question-points text-xs text-gray-400 dark:text-slate-500">${parseInt(q.points)} pts</span>
                        </div>
                        <p class="exam-question-text text-sm text-gray-700 dark:text-slate-300 line-clamp-2">${escapeHtml(q.text)}</p>
                        ${q.block_name ? `<p class="text-xs text-orange-600 dark:text-orange-400 mt-1">${escapeHtml(q.block_name)}</p>` : ''}
                    </div>
                </label>
            `}).join('');
            lucide.createIcons();
        }

        function updateCourseFilters() {
            const options = '<option value="">All Courses</option>' + courses.map(c => `<option value="${c.code}">${c.code}</option>`).join('');
            const filterCourse = document.getElementById('filter-course');
            const examFilterCourse = document.getElementById('exam-filter-course');
            if (filterCourse) filterCourse.innerHTML = options;
            if (examFilterCourse) examFilterCourse.innerHTML = options;
        }

        function updateBankSelect() {
            document.getElementById('q-bank').innerHTML = '<option value="">Select a bank...</option>' +
                banks.map(b => `<option value="${b.id}">${b.course_code}/${b.name}</option>`).join('');
        }

        // New Bank Form (inline in question modal)
        function showNewBankForm() {
            const form = document.getElementById('new-bank-form');
            const courseSelect = document.getElementById('new-bank-course');
            // Populate course dropdown
            courseSelect.innerHTML = '<option value="">Select course...</option>' +
                courses.map(c => `<option value="${c.id}">${c.code}</option>`).join('');
            form.classList.remove('hidden');
            lucide.createIcons();
        }

        function hideNewBankForm() {
            document.getElementById('new-bank-form').classList.add('hidden');
            document.getElementById('new-bank-name').value = '';
        }

        async function createNewBank() {
            const courseId = document.getElementById('new-bank-course').value;
            const name = document.getElementById('new-bank-name').value.trim();

            if (!courseId) return alert('Please select a course');
            if (!name) return alert('Please enter a bank name');

            try {
                const newBank = await api('banks/', 'POST', { course: courseId, name });
                // Reload banks and select the new one
                await loadBanks();
                document.getElementById('q-bank').value = newBank.id;
                hideNewBankForm();
            } catch (err) {
                alert('Failed to create bank: ' + (err.message || err));
            }
        }

        // New Course Form (nested in new bank form)
        function showNewCourseForm() {
            document.getElementById('new-course-form').classList.remove('hidden');
            lucide.createIcons();
        }

        function hideNewCourseForm() {
            document.getElementById('new-course-form').classList.add('hidden');
            document.getElementById('new-course-code').value = '';
            document.getElementById('new-course-name').value = '';
        }

        async function createNewCourse() {
            const code = document.getElementById('new-course-code').value.trim();
            const name = document.getElementById('new-course-name').value.trim();

            if (!code) return alert('Please enter a course code');

            try {
                const newCourse = await api('courses/', 'POST', { code, name: name || code });
                // Reload courses and update the course dropdown
                await loadCourses();
                // Update the new-bank-course dropdown and select the new course
                const courseSelect = document.getElementById('new-bank-course');
                courseSelect.innerHTML = '<option value="">Select course...</option>' +
                    courses.map(c => `<option value="${c.id}">${c.code}</option>`).join('');
                courseSelect.value = newCourse.id;
                hideNewCourseForm();
            } catch (err) {
                alert('Failed to create course: ' + (err.message || err));
            }
        }

        // Question Modal
        async function openNewQuestion() {
            editingQuestionId = null;
            window.currentQuestion = null;
            window.linkedQuestions = [];
            window.blockVariants = [];
            // Clear images gallery
            loadQuestionImages(null);
            document.getElementById('modal-title').textContent = 'New Question';
            document.getElementById('delete-btn').classList.add('hidden');
            document.getElementById('linked-tabs').classList.add('hidden');
            document.getElementById('linked-tabs').innerHTML = '';
            document.getElementById('block-tabs-container').classList.add('hidden');
            document.getElementById('block-tabs').innerHTML = '';
            document.getElementById('sync-section').classList.add('hidden');
            document.getElementById('block-section').classList.add('hidden');
            document.getElementById('q-bank').value = '';
            document.getElementById('q-type').value = 'multipleChoice';
            document.getElementById('q-points').value = '2';
            document.getElementById('q-difficulty').value = 'medium';
            document.getElementById('q-tags').value = '';
            pendingEditorValue = '';
            if (editor) editor.setValue('');
            updateAnswerFields();
            showModal('question-modal');
            // Load Monaco lazily
            await loadMonaco();
        }

        async function editQuestion(id) {
            try {
                // Ensure banks are loaded before editing
                if (!banks.length) {
                    await loadBanks();
                }
                const q = await api(`questions/${id}/`);
                editingQuestionId = id;
                window.currentQuestion = q;
                document.getElementById('modal-title').textContent = 'Edit Question';
                document.getElementById('delete-btn').classList.remove('hidden');
                // Update the bank select first, then set the value
                updateBankSelect();
                document.getElementById('q-bank').value = q.question_bank;
                document.getElementById('q-type').value = q.question_type;
                document.getElementById('q-points').value = q.points;
                document.getElementById('q-difficulty').value = q.difficulty;
                document.getElementById('q-tags').value = (q.tags || []).map(t => t.name).join(', ');
                pendingEditorValue = q.text;
                updateAnswerFields(q.answer_data);
                // Update block section
                updateBlockSection(q);
                // Load and display linked questions (don't await - let it update in background)
                updateLinkedSection(q);
                // Load images for this question
                loadQuestionImages(id);
                // Ensure modal stays visible
                showModal('question-modal');
                // Load Monaco lazily then set value
                await loadMonaco();
                if (editor) editor.setValue(pendingEditorValue || '');
            } catch (err) {
                console.error('Error editing question:', err);
            }
        }

        async function updateBlockSection(q) {
            const blockSection = document.getElementById('block-section');
            const createBlockSection = document.getElementById('create-block-section');
            const blockTabsContainer = document.getElementById('block-tabs-container');
            const blockTabs = document.getElementById('block-tabs');
            const blockTabsLabel = document.getElementById('block-tabs-label');

            if (q.block && q.block_name) {
                // Show block info, hide create block option
                blockSection.classList.remove('hidden');
                createBlockSection?.classList.add('hidden');
                document.getElementById('block-max-display').textContent = `Exam will pick ${q.block_max_questions} of ${q.block_variant_count} variants from "${q.block_name}"`;
                lucide.createIcons();

                // Fetch variants and show tabs (always show container so Add Variant button is visible)
                const variants = await api(`blocks/${q.block}/questions/`);
                window.blockVariants = variants;

                blockTabsContainer.classList.remove('hidden');
                blockTabsLabel.textContent = `${q.block_name} (pick ${q.block_max_questions})`;

                blockTabs.innerHTML = variants.map((v, idx) => {
                    const isActive = v.id === q.id;
                    return `
                        <button
                            onclick="event.stopPropagation(); switchToVariant(${v.id})"
                            class="px-3 py-1.5 rounded-lg text-sm font-medium whitespace-nowrap transition-all ${
                                isActive
                                    ? 'bg-orange-500 text-white shadow-sm'
                                    : 'bg-gray-100 dark:bg-slate-700 text-gray-600 dark:text-slate-300 hover:bg-gray-200 dark:hover:bg-slate-600'
                            }"
                            title="${escapeHtml(v.text.substring(0, 80))}"
                        >
                            V${idx + 1}
                        </button>
                    `;
                }).join('');
                lucide.createIcons();
            } else {
                // No block - show create block option (only for existing questions)
                blockSection.classList.add('hidden');
                blockTabsContainer.classList.add('hidden');
                blockTabs.innerHTML = '';
                // Only show create block for existing questions (not new ones)
                if (q.id && createBlockSection) {
                    createBlockSection.classList.remove('hidden');
                    lucide.createIcons();
                } else if (createBlockSection) {
                    createBlockSection.classList.add('hidden');
                }
            }
        }

        async function switchToVariant(questionId) {
            // Switch to variant - just update the current modal
            await editQuestion(questionId);
        }

        async function addBlockVariant() {
            if (!window.currentQuestion?.block) return;
            const q = window.currentQuestion;
            const blockVariants = window.blockVariants || [];

            // Create a copy of the question in the same block
            const newQuestion = {
                question_bank: q.question_bank,
                question_type: q.question_type,
                text: q.text + '\n\n<!-- New variant - edit this question -->',
                points: q.points,
                difficulty: q.difficulty,
                answer_data: q.answer_data,
                block: q.block,
                variant_number: blockVariants.length + 1,
            };

            try {
                const created = await api('questions/', 'POST', newQuestion);
                // Switch to the new variant
                await editQuestion(created.id);
                showToast('Variant created', 'success');
            } catch (err) {
                console.error('Failed to create variant:', err);
                showToast('Failed to create variant', 'error');
            }
        }

        async function createBlockFromQuestion() {
            if (!window.currentQuestion?.id) return;
            const q = window.currentQuestion;

            // Prompt for block name
            const blockName = prompt('Enter a name for this block (e.g., "Week 3 Q1" or "SQL Join Question"):');
            if (!blockName) return;

            try {
                // Create a new block
                const block = await api('blocks/', 'POST', {
                    question_bank: q.question_bank,
                    name: blockName,
                    max_questions: 1, // Default: pick 1 variant per exam
                });

                // Update the current question to be in this block
                await api(`questions/${q.id}/`, 'PATCH', {
                    block: block.id,
                    variant_number: 1,
                });

                // Reload the question to show the block UI
                await editQuestion(q.id);
                showToast('Block created - add variants with "Add Variant" or "AI Variant"', 'success');
            } catch (err) {
                console.error('Failed to create block:', err);
                showToast('Failed to create block', 'error');
            }
        }

        function toggleAiVariantMenu() {
            const menu = document.getElementById('ai-variant-menu');
            menu.classList.toggle('hidden');
            lucide.createIcons();

            // Close on click outside
            if (!menu.classList.contains('hidden')) {
                setTimeout(() => {
                    document.addEventListener('click', closeAiVariantMenu, { once: true });
                }, 0);
            }
        }

        function closeAiVariantMenu(e) {
            const dropdown = document.getElementById('ai-variant-dropdown');
            if (!dropdown.contains(e?.target)) {
                document.getElementById('ai-variant-menu').classList.add('hidden');
            }
        }

        async function aiBlockVariant(targetType = 'same') {
            if (!window.currentQuestion?.block) return;
            const q = window.currentQuestion;

            // Close dropdown
            document.getElementById('ai-variant-menu').classList.add('hidden');

            // Show loading toast
            showToast('Generating AI variant...', 'info');

            try {
                // Call AI to generate a variant
                const response = await api('ai/generate-variant/', 'POST', {
                    question_id: q.id,
                    block_id: q.block,
                    target_type: targetType === 'same' ? null : targetType,
                });

                if (response.id) {
                    // Switch to the new AI-generated variant
                    await editQuestion(response.id);
                    showToast('AI variant created', 'success');
                } else if (response.error) {
                    showToast('AI generation failed: ' + response.error, 'error');
                }
            } catch (err) {
                console.error('AI variant generation failed:', err);
                showToast('Failed to generate AI variant. Check API key.', 'error');
            }
        }

        async function updateLinkedSection(q) {
            const linkedTabs = document.getElementById('linked-tabs');
            const syncSection = document.getElementById('sync-section');

            // Fetch linked questions if any
            const linked = await api(`questions/${q.id}/linked/`);
            window.linkedQuestions = linked;

            if (linked.length > 1) {
                linkedTabs.classList.remove('hidden');
                linkedTabs.innerHTML = linked.map(lq => {
                    const isActive = lq.id === q.id;
                    const isCanonical = !lq.canonical;
                    return `
                        <button
                            onclick="event.stopPropagation(); switchToLinked(${lq.id})"
                            class="px-3 py-1.5 rounded-lg text-sm font-medium whitespace-nowrap transition-all ${
                                isActive
                                    ? 'bg-sky-500 text-white shadow-sm'
                                    : 'bg-gray-100 dark:bg-slate-700 text-gray-600 dark:text-slate-300 hover:bg-gray-200 dark:hover:bg-slate-600'
                            }"
                        >
                            ${isCanonical ? '<i data-lucide="star" class="w-3 h-3 inline mr-1"></i>' : ''}${lq.course_code}/${lq.bank_name}
                        </button>
                    `;
                }).join('');
                lucide.createIcons();

                // Show sync button if this is not the canonical question
                if (q.canonical) {
                    syncSection.classList.remove('hidden');
                } else {
                    syncSection.classList.add('hidden');
                }
            } else {
                linkedTabs.classList.add('hidden');
                linkedTabs.innerHTML = '';
                syncSection.classList.add('hidden');
            }
        }

        async function switchToLinked(questionId) {
            // Check if we already have the linked question data cached
            const cachedQuestion = window.linkedQuestions?.find(q => q.id === questionId);
            if (cachedQuestion) {
                // Quick switch - reuse cached data for tabs
                await editQuestion(questionId);
            } else {
                await editQuestion(questionId);
            }
        }

        async function syncFromCanonical() {
            if (!window.currentQuestion?.canonical) return;
            if (!confirm('This will overwrite this question with the canonical version. Continue?')) return;
            await api(`questions/${editingQuestionId}/sync/`, 'POST');
            await editQuestion(editingQuestionId);
        }

        async function saveQuestion() {
            const data = {
                question_bank: parseInt(document.getElementById('q-bank').value),
                question_type: document.getElementById('q-type').value,
                text: editor?.getValue() || '',
                points: parseFloat(document.getElementById('q-points').value),
                difficulty: document.getElementById('q-difficulty').value,
                answer_data: getAnswerData(),
            };
            if (!data.question_bank) return alert('Please select a question bank');
            if (editingQuestionId) await api(`questions/${editingQuestionId}/`, 'PUT', data);
            else await api('questions/', 'POST', data);
            closeModal();
            await loadQuestions();
        }

        async function deleteQuestion() {
            if (!confirm('Delete this question?')) return;
            const q = window.currentQuestion;
            const wasInBlock = q?.block;
            const blockVariants = window.blockVariants || [];

            try {
                await api(`questions/${editingQuestionId}/`, 'DELETE');
            } catch (err) {
                console.error('Delete failed:', err);
                showToast('Failed to delete question', 'error');
                return;
            }

            // If this was a variant in a block, switch to another variant if available
            if (wasInBlock && blockVariants.length > 1) {
                const otherVariant = blockVariants.find(v => v.id !== editingQuestionId);
                if (otherVariant) {
                    await editQuestion(otherVariant.id);
                    showToast('Variant deleted', 'success');
                    return;
                }
            }

            closeModal();
            await loadQuestions();
            showToast('Question deleted', 'success');
        }

        function updateAnswerFields(data = {}) {
            const type = document.getElementById('q-type').value;
            const container = document.getElementById('answer-fields');
            if (type === 'multipleChoice') {
                container.innerHTML = `<div class="space-y-3">
                    <div><label class="block text-sm font-medium text-gray-700 dark:text-slate-300 mb-1">Correct Answer</label>
                    <input type="text" id="a-correct" value="${data.correct || ''}" class="input-modern w-full px-3 py-2 rounded-lg"></div>
                    <div><label class="block text-sm font-medium text-gray-700 dark:text-slate-300 mb-1">Wrong Answers (one per line)</label>
                    <textarea id="a-wrong" rows="3" class="input-modern w-full px-3 py-2 rounded-lg">${(data.wrong || []).join('\n')}</textarea></div>
                </div>`;
            } else if (type === 'trueFalse') {
                container.innerHTML = `<div><label class="block text-sm font-medium text-gray-700 dark:text-slate-300 mb-2">Correct Answer</label>
                <div class="flex gap-6"><label class="flex items-center gap-2"><input type="radio" name="tf" value="true" ${data.correct === true ? 'checked' : ''} class="w-4 h-4 text-sky-600"><span class="text-gray-900 dark:text-white">True</span></label>
                <label class="flex items-center gap-2"><input type="radio" name="tf" value="false" ${data.correct === false ? 'checked' : ''} class="w-4 h-4 text-sky-600"><span class="text-gray-900 dark:text-white">False</span></label></div></div>`;
            } else if (type === 'shortAnswer') {
                const lineLength = data.lineLength || '';
                container.innerHTML = `<div class="space-y-3">
                    <div><label class="block text-sm font-medium text-gray-700 dark:text-slate-300 mb-1">Solution</label>
                    <textarea id="a-solution" rows="3" class="input-modern w-full px-3 py-2 rounded-lg">${data.solution || ''}</textarea></div>
                    <div><label class="block text-sm font-medium text-gray-700 dark:text-slate-300 mb-1">Answer Line Length</label>
                    <select id="a-lineLength" class="input-modern w-full px-3 py-2 rounded-lg">
                        <option value="" ${lineLength === '' ? 'selected' : ''}>Inherit from exam settings</option>
                        <option value="1in" ${lineLength === '1in' ? 'selected' : ''}>1 inch</option>
                        <option value="2in" ${lineLength === '2in' ? 'selected' : ''}>2 inches</option>
                        <option value="3in" ${lineLength === '3in' ? 'selected' : ''}>3 inches</option>
                        <option value="4in" ${lineLength === '4in' ? 'selected' : ''}>4 inches</option>
                        <option value="5in" ${lineLength === '5in' ? 'selected' : ''}>5 inches</option>
                        <option value="\\linewidth" ${lineLength === '\\linewidth' ? 'selected' : ''}>Full width</option>
                    </select>
                    <p class="text-xs text-gray-400 dark:text-slate-500 mt-1">Leave as "Inherit" to use the exam's default line length</p></div>
                </div>`;
            } else if (type === 'longAnswer') {
                const solutionSpace = data.solutionSpace || '';
                container.innerHTML = `<div class="space-y-3">
                    <div><label class="block text-sm font-medium text-gray-700 dark:text-slate-300 mb-1">Solution</label>
                    <textarea id="a-solution" rows="3" class="input-modern w-full px-3 py-2 rounded-lg">${data.solution || ''}</textarea></div>
                    <div><label class="block text-sm font-medium text-gray-700 dark:text-slate-300 mb-1">Solution Space</label>
                    <select id="a-solutionSpace" class="input-modern w-full px-3 py-2 rounded-lg">
                        <option value="" ${solutionSpace === '' ? 'selected' : ''}>Inherit from exam settings</option>
                        <option value="1in" ${solutionSpace === '1in' ? 'selected' : ''}>1 inch</option>
                        <option value="1.5in" ${solutionSpace === '1.5in' ? 'selected' : ''}>1.5 inches</option>
                        <option value="2in" ${solutionSpace === '2in' ? 'selected' : ''}>2 inches</option>
                        <option value="3in" ${solutionSpace === '3in' ? 'selected' : ''}>3 inches</option>
                        <option value="4in" ${solutionSpace === '4in' ? 'selected' : ''}>4 inches</option>
                        <option value="\\stretch{1}" ${solutionSpace === '\\stretch{1}' ? 'selected' : ''}>Fill page</option>
                    </select>
                    <p class="text-xs text-gray-400 dark:text-slate-500 mt-1">Leave as "Inherit" to use the exam's default solution space</p></div>
                </div>`;
            } else {
                container.innerHTML = `<div><label class="block text-sm font-medium text-gray-700 dark:text-slate-300 mb-1">Solution</label>
                <textarea id="a-solution" rows="3" class="input-modern w-full px-3 py-2 rounded-lg">${data.solution || ''}</textarea></div>`;
            }
        }

        function getAnswerData() {
            const type = document.getElementById('q-type').value;
            if (type === 'multipleChoice') return { correct: document.getElementById('a-correct').value, wrong: document.getElementById('a-wrong').value.split('\n').filter(x => x.trim()) };
            if (type === 'trueFalse') return { correct: document.querySelector('input[name="tf"]:checked')?.value === 'true' };
            if (type === 'shortAnswer') {
                const data = { solution: document.getElementById('a-solution')?.value || '' };
                const lineLength = document.getElementById('a-lineLength')?.value;
                if (lineLength) data.lineLength = lineLength;
                return data;
            }
            if (type === 'longAnswer') {
                const data = { solution: document.getElementById('a-solution')?.value || '' };
                const solutionSpace = document.getElementById('a-solutionSpace')?.value;
                if (solutionSpace) data.solutionSpace = solutionSpace;
                return data;
            }
            return { solution: document.getElementById('a-solution')?.value || '' };
        }

        // Course Modal
        function openNewCourse() {
            document.getElementById('c-code').value = '';
            document.getElementById('c-name').value = '';
            document.getElementById('c-description').value = '';
            showModal('course-modal');
        }

        async function saveCourse() {
            await api('courses/', 'POST', {
                code: document.getElementById('c-code').value,
                name: document.getElementById('c-name').value,
                description: document.getElementById('c-description').value,
            });
            closeCourseModal();
            await loadCourses();
        }

        function closeCourseModal() { hideModal('course-modal'); }

        // Exam Templates
        let examTemplates = [];
        let currentTemplateId = null;
        let currentTemplateCourse = ''; // Track current template's course code

        let currentTemplateFilter = ''; // Track current quiz filter

        // Session persistence for template creation
        let sessionInstructor = localStorage.getItem('templateSessionInstructor') || '';
        let sessionTerm = localStorage.getItem('templateSessionTerm') || '';
        let sessionType = localStorage.getItem('templateSessionType') || 'exam';
        let sessionCourseCode = localStorage.getItem('templateSessionCourseCode') || '';

        // Multi-version preview state
        let versionPreviewData = null; // Stores {versions: [...], blocks: [...]}
        let currentPreviewVersion = 'A'; // Currently displayed version tab

        async function loadExamTemplates(isQuiz = '') {
            currentTemplateFilter = isQuiz;
            const params = new URLSearchParams();
            if (isQuiz !== '') params.append('is_quiz', isQuiz);
            const data = await api(`exams/templates/?${params.toString()}`);
            examTemplates = data.results || data || [];

            // Populate course dropdown with ALL courses (from global courses array)
            const courseSelector = document.getElementById('template-course-selector');
            let courseHtml = '<option value="">All Courses</option>';
            (courses || []).forEach(c => {
                courseHtml += `<option value="${c.code}">${c.code}</option>`;
            });
            courseSelector.innerHTML = courseHtml;

            // Populate template dropdown (all templates initially)
            filterTemplatesByCourse('');
        }

        function filterTemplatesByCourse(courseCode) {
            const selector = document.getElementById('template-selector');
            let html = '<option value="">Select a template...</option>';

            const filtered = courseCode
                ? examTemplates.filter(t => (t.course_code || 'No Course') === courseCode)
                : examTemplates;

            filtered.forEach(t => {
                const typeTag = t.is_quiz ? ' [Quiz]' : '';
                const filterCount = t.filter_count || 0;
                const filterBadge = filterCount > 0 ? ` [${filterCount} filters]` : '';
                const ownerTag = t.is_owner ? '' : t.is_shared ? ` (shared by ${t.owner_username})` : '';
                html += `<option value="${t.id}">${escapeHtml(t.name)}${typeTag}${filterBadge}${ownerTag}</option>`;
            });

            selector.innerHTML = html;
        }

        async function loadExamTemplate(templateId) {
            if (!templateId) {
                currentTemplateId = null;
                currentTemplateCourse = '';
                document.getElementById('delete-template-btn').classList.add('hidden');
                document.getElementById('share-template-btn')?.classList.add('hidden');
                document.getElementById('copy-template-btn')?.classList.add('hidden');
                updateActiveFiltersDisplay(null);

                // Clear form fields for new template
                document.getElementById('exam-title').value = '';
                document.getElementById('exam-course').value = '';
                document.getElementById('exam-instructor').value = '';
                document.getElementById('exam-term').value = '';
                document.getElementById('exam-instructions').value = '';
                document.getElementById('exam-answers').checked = true;
                document.getElementById('exam-line-length').value = '3in';
                document.getElementById('exam-solution-space').value = '1.5in';
                document.getElementById('exam-quiz-mode').checked = false;
                document.getElementById('exam-include-id').checked = true;
                document.getElementById('exam-split-mc').checked = false;
                toggleQuizModeOptions();

                // Clear sections
                examSections = [];
                sectionIdCounter = 0;
                renderExamSections();

                // Clear preview
                const previewContainer = document.getElementById('exam-preview');
                if (previewContainer) {
                    previewContainer.innerHTML = '<div class="text-center py-8 text-gray-400"><p>Add sections and questions to see preview</p></div>';
                }

                return;
            }

            // Show loading indicator in preview
            const previewContainer = document.getElementById('exam-preview');
            if (previewContainer) {
                previewContainer.innerHTML = '<div class="text-center py-6"><i data-lucide="loader-2" class="w-6 h-6 animate-spin mx-auto text-sky-500"></i><p class="text-sm text-gray-500 mt-2">Loading template...</p></div>';
                lucide.createIcons();
            }

            try {
            // Fetch full template details
            const template = await api(`exams/templates/${templateId}/`);
            if (!template) {
                previewContainer.innerHTML = '<div class="text-center py-6 text-red-500">Failed to load template</div>';
                return;
            }

            currentTemplateId = templateId;
            currentTemplateCourse = template.course_code || '';

            // Clear question cache when loading a new template
            cachedSectionQuestions = {};
            cachedFinalQuestions = null;
            hasCachedQuestions = false;
            // Don't clear localStorage here - we want to restore previous selection

            // Show template action buttons based on ownership
            const isOwner = template.is_owner;
            document.getElementById('delete-template-btn').classList.toggle('hidden', !isOwner);
            document.getElementById('share-template-btn')?.classList.toggle('hidden', !isOwner);
            // Show copy button for everyone (owners and shared users)
            document.getElementById('copy-template-btn')?.classList.remove('hidden');

            // Fill in the form fields
            document.getElementById('exam-title').value = template.name || '';
            document.getElementById('exam-course').value = template.course_code || '';
            document.getElementById('exam-instructor').value = template.instructor || '';
            document.getElementById('exam-term').value = template.term || '';
            document.getElementById('exam-instructions').value = template.instructions || '';
            document.getElementById('exam-answers').checked = true;

            // Answer formatting settings
            const lineLengthSelect = document.getElementById('exam-line-length');
            if (lineLengthSelect && template.default_line_length) {
                lineLengthSelect.value = template.default_line_length;
            }
            const solutionSpaceSelect = document.getElementById('exam-solution-space');
            if (solutionSpaceSelect && template.default_solution_space) {
                solutionSpaceSelect.value = template.default_solution_space;
            }

            // Quiz mode settings
            const quizModeCheckbox = document.getElementById('exam-quiz-mode');
            if (quizModeCheckbox) {
                quizModeCheckbox.checked = template.is_quiz || false;
                toggleQuizModeOptions();
            }
            const includeIdCheckbox = document.getElementById('exam-include-id');
            if (includeIdCheckbox) {
                includeIdCheckbox.checked = template.include_id_field ?? true;
            }

            // Template-level point constraints
            document.getElementById('exam-max-points').value = template.max_points || '';
            document.getElementById('exam-max-mc-points').value = template.max_mc_points || '';
            document.getElementById('exam-max-tf-points').value = template.max_tf_points || '';
            document.getElementById('exam-max-short-points').value = template.max_short_points || '';
            document.getElementById('exam-max-long-points').value = template.max_long_points || '';

            // Sync target points in sidebar with template max_points
            // If template has max_points, use that; otherwise calculate from selected questions
            const targetPointsInput = document.getElementById('target-points');
            if (targetPointsInput) {
                if (template.max_points) {
                    targetPointsInput.value = template.max_points;
                } else {
                    // Calculate total points from selected questions
                    const totalPoints = Array.from(selectedQuestions).reduce((sum, qId) => {
                        const row = document.querySelector(`tr[data-question-id="${qId}"]`);
                        if (row) {
                            const pointsCell = row.querySelector('td:nth-child(4)');
                            if (pointsCell) {
                                return sum + (parseFloat(pointsCell.textContent) || 0);
                            }
                        }
                        return sum;
                    }, 0);
                    targetPointsInput.value = totalPoints || '';
                }
                updateTargetIndicator();
            }

            // Load sections from selection_rules
            examSections = [];
            sectionIdCounter = 0;

            if (template.selection_rules) {
                // Load include_answers and versions if present
                if (template.selection_rules.include_answers !== undefined) {
                    document.getElementById('exam-answers').checked = template.selection_rules.include_answers;
                }
                if (template.selection_rules.versions !== undefined) {
                    document.getElementById('exam-versions').value = template.selection_rules.versions;
                }

                // Check if it's the new object format with sections property
                const sectionsData = template.selection_rules.sections ||
                    (Array.isArray(template.selection_rules) ? template.selection_rules : null);

                if (sectionsData && Array.isArray(sectionsData) && sectionsData.length > 0) {
                    for (const rule of sectionsData) {
                        const id = ++sectionIdCounter;
                        examSections.push({
                            id,
                            name: rule.name || `Section ${id}`,
                            course: rule.course || template.course_code || '',
                            tags: rule.tags || [],
                            type: rule.type || '',
                            count: rule.count || 5,
                            maxPoints: rule.maxPoints || null,
                            maxMCPoints: rule.maxMCPoints || null,
                            maxTFPoints: rule.maxTFPoints || null,
                            maxShortPoints: rule.maxShortPoints || null,
                            maxLongPoints: rule.maxLongPoints || null,
                            questions: []
                        });
                    }
                }
                // Check if it's the old INI-based format (include_files)
                else if (template.selection_rules.include_files && Array.isArray(template.selection_rules.include_files) && template.selection_rules.include_files.length > 0) {
                    // Convert include_files to tags (e.g., "quizPool/week1.txt" -> "Week 1")
                    const tagSet = new Set();
                    template.selection_rules.include_files.forEach(file => {
                        const match = file.match(/week(\d+)/i);
                        if (match) {
                            tagSet.add(`Week ${match[1]}`);
                        } else {
                            // Try to extract a reasonable tag name from basename
                            const basename = file.split('/').pop().replace('.txt', '');
                            if (basename) tagSet.add(basename);
                        }
                    });
                    const tags = Array.from(tagSet);

                    if (tags.length > 0) {
                        const id = ++sectionIdCounter;
                        examSections.push({
                            id,
                            name: 'Main',
                            course: template.course_code || '',
                            tags: tags,
                            type: '',
                            count: 10,
                            questions: []
                        });
                    }
                }
            }

            // If still no sections but we have filter_tags, create a section from those
            if (examSections.length === 0 && template.filter_tags_data && template.filter_tags_data.length > 0) {
                const id = ++sectionIdCounter;
                examSections.push({
                    id,
                    name: 'Filtered Questions',
                    course: template.course_code || '',
                    tags: template.filter_tags_data.map(t => t.name),
                    type: template.filter_question_types?.[0] || '',
                    count: 10,
                    questions: []
                });
            }

            // Always render sections (even if empty, to clear previous sections)
            renderExamSections();
            if (examSections.length > 0) {
                await refreshExamPreview();
            } else {
                // Clear preview if no sections
                const previewContainer = document.getElementById('exam-preview');
                if (previewContainer) {
                    previewContainer.innerHTML = '<div class="text-center py-8 text-gray-400"><p>No sections defined. Add sections to build your exam.</p></div>';
                }
            }

            // Update active filters display
            updateActiveFiltersDisplay(template);

            lucide.createIcons();
            saveViewState();
            } catch (err) {
                console.error('Error loading template:', err);
                showToast('Error loading template', 'error');
            }
        }

        function updateActiveFiltersDisplay(template) {
            const container = document.getElementById('active-filters');
            if (!template) {
                container.classList.add('hidden');
                return;
            }

            const filters = [];
            if (template.filter_weeks && template.filter_weeks.length > 0) {
                filters.push(`<span class="px-2 py-1 bg-amber-100 dark:bg-amber-900/50 text-amber-700 dark:text-amber-300 rounded">${template.filter_weeks.length} week(s)</span>`);
            }
            if (template.filter_question_types && template.filter_question_types.length > 0) {
                filters.push(`<span class="px-2 py-1 bg-blue-100 dark:bg-blue-900/50 text-blue-700 dark:text-blue-300 rounded">${template.filter_question_types.map(formatType).join(', ')}</span>`);
            }
            if (template.filter_banks_data && template.filter_banks_data.length > 0) {
                filters.push(`<span class="px-2 py-1 bg-green-100 dark:bg-green-900/50 text-green-700 dark:text-green-300 rounded">${template.filter_banks_data.length} bank(s)</span>`);
            }
            if (template.filter_tags_data && template.filter_tags_data.length > 0) {
                filters.push(`<span class="px-2 py-1 bg-purple-100 dark:bg-purple-900/50 text-purple-700 dark:text-purple-300 rounded">${template.filter_tags_data.map(t => t.name).join(', ')}</span>`);
            }
            if (template.filter_difficulty) {
                filters.push(`<span class="px-2 py-1 bg-red-100 dark:bg-red-900/50 text-red-700 dark:text-red-300 rounded">${template.filter_difficulty}</span>`);
            }
            if (template.max_questions) {
                filters.push(`<span class="px-2 py-1 bg-gray-100 dark:bg-slate-700 text-gray-700 dark:text-slate-300 rounded">max ${template.max_questions} questions</span>`);
            }

            if (filters.length > 0) {
                container.innerHTML = '<span class="text-gray-500 dark:text-slate-400">Active filters:</span>' + filters.join('');
                container.classList.remove('hidden');
            } else {
                container.classList.add('hidden');
            }
        }

        async function saveAsTemplate() {
            const title = document.getElementById('exam-title').value.trim();
            const courseCode = document.getElementById('exam-course').value.trim();

            if (!title) {
                showToast('Please enter an exam title', 'warning');
                return;
            }
            if (!courseCode) {
                showToast('Please enter a course code', 'warning');
                return;
            }

            // Find the course ID from the course code
            const course = courses.find(c => c.code === courseCode);
            if (!course) {
                alert(`Course "${courseCode}" not found. Please enter a valid course code.`);
                return;
            }

            // Save sections as selection_rules
            const sectionsToSave = examSections.map(s => ({
                name: s.name,
                course: s.course,
                tags: s.tags,
                type: s.type,
                count: s.count,
                maxPoints: s.maxPoints || null,
                maxMCPoints: s.maxMCPoints || null,
                maxTFPoints: s.maxTFPoints || null,
                maxShortPoints: s.maxShortPoints || null,
                maxLongPoints: s.maxLongPoints || null
            }));

            const templateData = {
                name: title,
                course: course.id,
                instructor: document.getElementById('exam-instructor').value || '',
                term: document.getElementById('exam-term').value || '',
                instructions: document.getElementById('exam-instructions').value || '',
                shuffle_questions: true, // Always shuffle within sections
                shuffle_answers: true,
                is_quiz: document.getElementById('exam-quiz-mode')?.checked || false,
                include_id_field: document.getElementById('exam-include-id')?.checked || false,
                default_line_length: document.getElementById('exam-line-length')?.value || '3in',
                default_solution_space: document.getElementById('exam-solution-space')?.value || '1.5in',
                selection_rules: {
                    sections: sectionsToSave,
                    include_answers: document.getElementById('exam-answers')?.checked || false,
                    versions: parseInt(document.getElementById('exam-versions')?.value) || 1
                },
                // Template-level point constraints (use target-points from sidebar if exam-max-points is empty)
                max_points: parseFloat(document.getElementById('exam-max-points')?.value) || parseFloat(document.getElementById('target-points')?.value) || null,
                max_mc_points: parseFloat(document.getElementById('exam-max-mc-points')?.value) || null,
                max_tf_points: parseFloat(document.getElementById('exam-max-tf-points')?.value) || null,
                max_short_points: parseFloat(document.getElementById('exam-max-short-points')?.value) || null,
                max_long_points: parseFloat(document.getElementById('exam-max-long-points')?.value) || null,
            };

            try {
                let result;
                if (currentTemplateId) {
                    // Update existing template
                    if (!confirm('Update the existing template with current settings?')) return;
                    result = await api(`exams/templates/${currentTemplateId}/`, 'PUT', templateData);
                } else {
                    // Create new template
                    result = await api('exams/templates/', 'POST', templateData);
                }

                if (result.id) {
                    const wasNew = !currentTemplateId;
                    currentTemplateId = result.id;
                    await loadExamTemplates('');
                    document.getElementById('template-selector').value = result.id;
                    document.getElementById('delete-template-btn').classList.remove('hidden');
                    showToast(wasNew ? 'Template saved' : 'Template updated', 'success');
                }
            } catch (err) {
                console.error('Failed to save template:', err);
                showToast('Failed to save template', 'error');
            }
        }

        async function deleteCurrentTemplate() {
            if (!currentTemplateId) return;
            if (!confirm('Delete this template? This cannot be undone.')) return;

            try {
                await api(`exams/templates/${currentTemplateId}/`, 'DELETE');
                currentTemplateId = null;
                document.getElementById('template-selector').value = '';
                document.getElementById('delete-template-btn').classList.add('hidden');
                updateActiveFiltersDisplay(null);
                await loadExamTemplates('');
                showToast('Template deleted', 'success');
            } catch (err) {
                console.error('Failed to delete template:', err);
                showToast('Failed to delete template', 'error');
            }
        }

        // New Template Modal
        function openNewTemplateModal() {
            // Get course: session > filter > empty
            const currentCourseCode = sessionCourseCode
                || document.getElementById('template-course-selector')?.value
                || document.getElementById('filter-course')?.value
                || '';

            // Populate course dropdown
            const courseSelect = document.getElementById('new-template-course');
            courseSelect.innerHTML = '<option value="">Select a course...</option>';
            for (const course of courses) {
                const selected = course.code === currentCourseCode ? 'selected' : '';
                courseSelect.innerHTML += `<option value="${course.id}" data-code="${course.code}" ${selected}>${course.code} - ${course.name}</option>`;
            }

            // Use session values for instructor, term, and type (persisted across template creations)
            document.getElementById('new-template-name').value = '';
            document.getElementById('new-template-instructor').value = sessionInstructor;
            document.getElementById('new-template-term').value = sessionTerm;
            document.querySelector(`input[name="new-template-type"][value="${sessionType}"]`).checked = true;

            showModal('new-template-modal');
        }

        async function createNewTemplate() {
            const name = document.getElementById('new-template-name').value.trim();
            const courseSelect = document.getElementById('new-template-course');
            const courseId = courseSelect.value;
            const courseCode = courseSelect.selectedOptions[0]?.dataset?.code || '';
            const templateType = document.querySelector('input[name="new-template-type"]:checked').value;
            const isQuiz = templateType === 'quiz';
            const instructor = document.getElementById('new-template-instructor').value.trim();
            const term = document.getElementById('new-template-term').value.trim();

            // Save session values for next template creation
            sessionInstructor = instructor;
            sessionTerm = term;
            sessionType = templateType;
            sessionCourseCode = courseCode;
            localStorage.setItem('templateSessionInstructor', instructor);
            localStorage.setItem('templateSessionTerm', term);
            localStorage.setItem('templateSessionType', templateType);
            localStorage.setItem('templateSessionCourseCode', courseCode);

            if (!name) {
                showToast('Please enter a template name', 'warning');
                return;
            }
            if (!courseId) {
                showToast('Please select a course', 'warning');
                return;
            }

            const templateData = {
                name,
                course: courseId,
                is_quiz: isQuiz,
                instructor,
                term,
                shuffle_questions: true,
                include_id_field: true,
                default_line_length: '3in',
                default_solution_space: '1.5in',
                selection_rules: [],
            };

            try {
                const result = await api('exams/templates/', 'POST', templateData);
                if (result.id) {
                    hideModal('new-template-modal');
                    await loadExamTemplates('');
                    document.getElementById('template-selector').value = result.id;
                    await loadExamTemplate(result.id);
                    // Auto-add first section
                    addExamSection();
                    showToast('Template created', 'success');
                }
            } catch (err) {
                console.error('Failed to create template:', err);
                showToast('Failed to create template', 'error');
            }
        }

        // Exam Builder
        function toggleQuestion(id, points, checked) {
            if (checked) selectedQuestions.add(id);
            else selectedQuestions.delete(id);
            updateExamStats();
            loadExamQuestions(); // re-render to update visual state
        }

        function updateExamStats() {
            document.getElementById('selected-count').textContent = selectedQuestions.size;
            // Calculate total points from current exam questions
            const totalPoints = currentExamQuestions.reduce((sum, q) => sum + (parseFloat(q.points) || 0), 0);
            document.getElementById('selected-points').textContent = totalPoints;
            // Update target indicator
            updateTargetIndicator();
        }

        // Update the target indicator to show if we're above/below target
        function updateTargetIndicator() {
            const indicator = document.getElementById('target-indicator');
            const targetInput = document.getElementById('target-points');
            const pointsEl = document.getElementById('selected-points');

            if (!indicator || !targetInput || !pointsEl) return;

            const target = parseFloat(targetInput.value) || 0;
            const current = parseFloat(pointsEl.textContent) || 0;

            if (target <= 0) {
                indicator.classList.add('hidden');
                return;
            }

            indicator.classList.remove('hidden');
            const diff = current - target;
            const percent = Math.round((current / target) * 100);

            if (diff >= 0) {
                // At or above target
                indicator.className = 'mb-4 p-2 rounded-lg text-sm font-medium text-center bg-emerald-100 dark:bg-emerald-900/50 text-emerald-700 dark:text-emerald-300';
                indicator.innerHTML = `<i data-lucide="check-circle" class="w-4 h-4 inline mr-1"></i>${percent}% of target (+${diff} pts)`;
            } else {
                // Below target
                indicator.className = 'mb-4 p-2 rounded-lg text-sm font-medium text-center bg-amber-100 dark:bg-amber-900/50 text-amber-700 dark:text-amber-300';
                indicator.innerHTML = `<i data-lucide="alert-circle" class="w-4 h-4 inline mr-1"></i>${percent}% of target (${diff} pts)`;
            }
            lucide.createIcons();
        }

        // Balance the exam to meet the target points
        async function balanceForTarget() {
            const targetInput = document.getElementById('target-points');
            const target = parseFloat(targetInput.value) || 0;

            if (target <= 0) {
                alert('Please set a target points value first.');
                return;
            }

            const currentPoints = currentExamQuestions.reduce((sum, q) => sum + (parseFloat(q.points) || 0), 0);

            if (currentPoints >= target) {
                // Already at or above target - maybe remove some questions
                const sortedByPoints = [...currentExamQuestions].sort((a, b) => (parseFloat(a.points) || 0) - (parseFloat(b.points) || 0));
                let newTotal = currentPoints;
                let removed = 0;

                while (newTotal > target * 1.1 && sortedByPoints.length > 0) {
                    const q = sortedByPoints.pop(); // Remove highest point question
                    newTotal -= (parseFloat(q.points) || 0);
                    removeQuestionFromExam(q.id);
                    removed++;
                }

                if (removed > 0) {
                    showToast(`Removed ${removed} question(s) to reduce points closer to target`, 'success');
                } else {
                    showToast('Already at target - no changes made', 'info');
                }
            } else {
                // Need more questions - try to add from available pool
                // Get questions from each section that aren't already selected
                let addedCount = 0;
                let currentTotal = currentPoints;

                for (const section of examSections) {
                    if (currentTotal >= target) break;

                    const params = new URLSearchParams();
                    if (section.course) params.append('course', section.course);
                    if (section.type) params.append('type', section.type);
                    section.tags.forEach(t => params.append('tags', t));
                    params.append('page_size', 50);

                    try {
                        const data = await api(`questions/?${params.toString()}`);
                        const availableQuestions = (data.results || data || [])
                            .filter(q => !selectedQuestions.has(q.id))
                            .sort(() => Math.random() - 0.5);

                        for (const q of availableQuestions) {
                            if (currentTotal >= target) break;

                            q._section = section.name;
                            currentExamQuestions.push(q);
                            selectedQuestions.add(q.id);
                            currentTotal += (parseFloat(q.points) || 0);
                            addedCount++;
                        }
                    } catch (e) {
                        console.error('Error fetching questions for section:', section.name, e);
                    }
                }

                if (addedCount > 0) {
                    // Update the cache
                    cachedFinalQuestions = currentExamQuestions;
                    if (currentTemplateId) {
                        localStorage.setItem(`examQuestionIds_${currentTemplateId}`, JSON.stringify(currentExamQuestions.map(q => q.id)));
                    }
                    // Re-render preview
                    refreshExamPreview();
                    showToast(`Added ${addedCount} question(s) to reach target`, 'success');
                } else {
                    showToast('No additional questions available to add', 'warning');
                }
            }
        }

        // Select all visible questions in the exam builder
        function selectAllExamQuestions() {
            const questionCards = document.querySelectorAll('#exam-questions-list label[data-question-id]');
            questionCards.forEach(card => {
                const qid = parseInt(card.getAttribute('data-question-id'));
                if (qid && !selectedQuestions.has(qid)) {
                    selectedQuestions.add(qid);
                }
                // Update visual state immediately
                const checkbox = card.querySelector('input[type="checkbox"]');
                if (checkbox) checkbox.checked = true;
                card.classList.add('bg-sky-50', 'dark:bg-sky-900/30', 'ring-1', 'ring-sky-200', 'dark:ring-sky-700');
            });
            updateExamStats();
        }

        // Deselect all questions in the exam builder
        function deselectAllExamQuestions() {
            selectedQuestions.clear();
            const questionCards = document.querySelectorAll('#exam-questions-list label[data-question-id]');
            questionCards.forEach(card => {
                // Update visual state immediately
                const checkbox = card.querySelector('input[type="checkbox"]');
                if (checkbox) checkbox.checked = false;
                card.classList.remove('bg-sky-50', 'dark:bg-sky-900/30', 'ring-1', 'ring-sky-200', 'dark:ring-sky-700');
            });
            updateExamStats();
        }

        // Section-based exam builder
        let examSections = [];
        let sectionIdCounter = 0;

        function addExamSection() {
            const id = ++sectionIdCounter;
            // Default to current template's course, or fall back to filter selections
            const defaultCourse = currentTemplateCourse
                || document.getElementById('template-course-selector')?.value
                || document.getElementById('filter-course')?.value
                || '';
            const section = {
                id,
                name: `Section ${examSections.length + 1}`,
                course: defaultCourse,
                tags: [],
                type: '',
                count: null, // null = use all available questions
                maxPoints: null,
                maxMCPoints: null,
                maxTFPoints: null,
                maxShortPoints: null,
                maxLongPoints: null,
                questions: []
            };
            examSections.push(section);
            renderExamSections();
            // Load tags for the default course if one was set
            if (defaultCourse) {
                loadSectionTags(id);
            }
            saveViewState();
        }

        function removeExamSection(id) {
            examSections = examSections.filter(s => s.id !== id);
            renderExamSections();
            updateExamStats();
            saveViewState();
        }

        function renderExamSections() {
            const container = document.getElementById('exam-sections');
            if (!examSections.length) {
                container.innerHTML = `
                    <div class="text-center py-8 text-gray-400 dark:text-slate-500">
                        <i data-lucide="layout-list" class="w-10 h-10 mx-auto mb-2 opacity-50"></i>
                        <p>Click "Add Section" to start building your exam</p>
                        <p class="text-xs mt-1">Each section can have different tags and question counts</p>
                    </div>`;
                lucide.createIcons();
                return;
            }

            container.innerHTML = examSections.map((s, idx) => `
                <div class="border border-gray-200 dark:border-slate-700 rounded-xl p-4 bg-gray-50 dark:bg-slate-800/50" data-section-id="${s.id}">
                    <div class="mb-2">
                        <input type="text" value="${escapeHtml(s.name)}" onchange="updateSectionName(${s.id}, this.value)"
                            class="font-medium text-gray-900 dark:text-white bg-transparent border-none focus:outline-none focus:ring-2 focus:ring-sky-500 rounded px-1 -ml-1 w-full">
                    </div>
                    <div class="flex items-center justify-between mb-3">
                        <div class="flex items-center gap-2 flex-wrap" id="section-selected-${s.id}">
                            ${s.course ? `<span class="badge bg-sky-100 dark:bg-sky-900/50 text-sky-700 dark:text-sky-300 text-xs">${escapeHtml(s.course)}</span>` : ''}
                            ${s.tags.map(t => `<span class="badge bg-purple-100 dark:bg-purple-900/50 text-purple-700 dark:text-purple-300 text-xs">${escapeHtml(t)}</span>`).join('')}
                        </div>
                        <button onclick="removeExamSection(${s.id})" class="text-red-500 hover:text-red-700 p-1 flex-shrink-0">
                            <i data-lucide="trash-2" class="w-4 h-4"></i>
                        </button>
                    </div>
                    <div class="grid grid-cols-2 md:grid-cols-4 gap-3">
                        <div>
                            <label class="block text-xs text-gray-500 dark:text-slate-400 mb-1">Course</label>
                            <select onchange="updateSectionCourse(${s.id}, this.value)" class="input-modern w-full px-2 py-1.5 rounded-lg text-sm">
                                <option value="">All Courses</option>
                                ${(courses || []).map(c => `<option value="${c.code}" ${s.course === c.code ? 'selected' : ''}>${c.code}</option>`).join('')}
                            </select>
                        </div>
                        <div>
                            <label class="block text-xs text-gray-500 dark:text-slate-400 mb-1">Type</label>
                            <select onchange="updateSectionType(${s.id}, this.value)" class="input-modern w-full px-2 py-1.5 rounded-lg text-sm">
                                <option value="" ${!s.type ? 'selected' : ''}>All Types</option>
                                <option value="multipleChoice" ${s.type === 'multipleChoice' ? 'selected' : ''}>Multiple Choice</option>
                                <option value="trueFalse" ${s.type === 'trueFalse' ? 'selected' : ''}>True/False</option>
                                <option value="shortAnswer" ${s.type === 'shortAnswer' ? 'selected' : ''}>Short Answer</option>
                                <option value="longAnswer" ${s.type === 'longAnswer' ? 'selected' : ''}>Long Answer</option>
                            </select>
                        </div>
                        <div>
                            <label class="block text-xs text-gray-500 dark:text-slate-400 mb-1"># Questions</label>
                            <input type="number" value="${s.count || ''}" min="1" max="500" onchange="updateSectionCount(${s.id}, this.value)"
                                class="input-modern w-full px-2 py-1.5 rounded-lg text-sm" placeholder="All">
                        </div>
                        <div>
                            <label class="block text-xs text-gray-500 dark:text-slate-400 mb-1">Available</label>
                            <div class="px-2 py-1.5 text-sm font-medium text-sky-600" id="section-available-${s.id}">--</div>
                        </div>
                    </div>
                    <div class="mt-3">
                        <label class="block text-xs text-gray-500 dark:text-slate-400 mb-1">Tags (click to select)</label>
                        <div class="flex flex-wrap gap-1" id="section-tags-${s.id}">
                            <span class="text-xs text-gray-400">Loading tags...</span>
                        </div>
                    </div>
                    <details class="mt-3">
                        <summary class="text-xs text-gray-500 dark:text-slate-400 cursor-pointer hover:text-gray-700 dark:hover:text-slate-300">
                            Point Constraints (optional)
                        </summary>
                        <div class="grid grid-cols-2 md:grid-cols-5 gap-2 mt-2 p-2 bg-gray-100 dark:bg-slate-700/50 rounded-lg">
                            <div>
                                <label class="block text-xs text-gray-500 dark:text-slate-400 mb-1">Max Pts</label>
                                <input type="number" value="${s.maxPoints || ''}" min="0" placeholder="--"
                                    onchange="updateSectionConstraint(${s.id}, 'maxPoints', this.value)"
                                    class="input-modern w-full px-2 py-1 rounded text-xs">
                            </div>
                            <div>
                                <label class="block text-xs text-gray-500 dark:text-slate-400 mb-1">MC Pts</label>
                                <input type="number" value="${s.maxMCPoints || ''}" min="0" placeholder="--"
                                    onchange="updateSectionConstraint(${s.id}, 'maxMCPoints', this.value)"
                                    class="input-modern w-full px-2 py-1 rounded text-xs">
                            </div>
                            <div>
                                <label class="block text-xs text-gray-500 dark:text-slate-400 mb-1">T/F Pts</label>
                                <input type="number" value="${s.maxTFPoints || ''}" min="0" placeholder="--"
                                    onchange="updateSectionConstraint(${s.id}, 'maxTFPoints', this.value)"
                                    class="input-modern w-full px-2 py-1 rounded text-xs">
                            </div>
                            <div>
                                <label class="block text-xs text-gray-500 dark:text-slate-400 mb-1">Short Pts</label>
                                <input type="number" value="${s.maxShortPoints || ''}" min="0" placeholder="--"
                                    onchange="updateSectionConstraint(${s.id}, 'maxShortPoints', this.value)"
                                    class="input-modern w-full px-2 py-1 rounded text-xs">
                            </div>
                            <div>
                                <label class="block text-xs text-gray-500 dark:text-slate-400 mb-1">Long Pts</label>
                                <input type="number" value="${s.maxLongPoints || ''}" min="0" placeholder="--"
                                    onchange="updateSectionConstraint(${s.id}, 'maxLongPoints', this.value)"
                                    class="input-modern w-full px-2 py-1 rounded text-xs">
                            </div>
                        </div>
                    </details>
                </div>
            `).join('');
            lucide.createIcons();

            // Load tags for each section
            examSections.forEach(s => loadSectionTags(s.id));
        }

        async function loadSectionTags(sectionId) {
            const section = examSections.find(s => s.id === sectionId);
            if (!section) return;

            let tagsData;
            if (section.course) {
                tagsData = await api(`tags/?course=${section.course}`);
            } else {
                tagsData = await api('tags/');
            }
            const tags = tagsData.results || tagsData || [];

            const container = document.getElementById(`section-tags-${sectionId}`);
            if (!container) return;

            container.innerHTML = tags.map(t => {
                const isSelected = section.tags.includes(t.name);
                return `<button type="button" onclick="toggleSectionTag(${sectionId}, '${escapeHtml(t.name)}')"
                    class="px-2 py-0.5 text-xs rounded-full transition-colors ${isSelected
                        ? 'bg-emerald-500 text-white'
                        : 'bg-gray-200 dark:bg-slate-700 text-gray-600 dark:text-slate-300 hover:bg-gray-300 dark:hover:bg-slate-600'
                    }">${escapeHtml(t.name)}</button>`;
            }).join('');

            // Update available count
            updateSectionAvailable(sectionId);
        }

        function toggleSectionTag(sectionId, tagName) {
            const section = examSections.find(s => s.id === sectionId);
            if (!section) return;

            if (section.tags.includes(tagName)) {
                section.tags = section.tags.filter(t => t !== tagName);
            } else {
                section.tags.push(tagName);
            }
            // Clear all caches so refresh will re-fetch
            hasCachedQuestions = false;
            cachedSectionQuestions = {};
            cachedFinalQuestions = null;
            if (currentTemplateId) {
                localStorage.removeItem(`examQuestionIds_${currentTemplateId}`);
            }
            loadSectionTags(sectionId); // Re-render tags
            saveViewState();
        }

        function updateSectionName(id, value) {
            const section = examSections.find(s => s.id === id);
            if (section) section.name = value;
            saveViewState();
        }

        function updateSectionCourse(id, value) {
            const section = examSections.find(s => s.id === id);
            if (section) {
                section.course = value;
                section.tags = []; // Reset tags when course changes
                loadSectionTags(id);
            }
            // Clear all caches so refresh will re-fetch
            hasCachedQuestions = false;
            cachedSectionQuestions = {};
            cachedFinalQuestions = null;
            if (currentTemplateId) {
                localStorage.removeItem(`examQuestionIds_${currentTemplateId}`);
            }
            saveViewState();
        }

        function updateSectionType(id, value) {
            const section = examSections.find(s => s.id === id);
            if (section) {
                section.type = value;
                updateSectionAvailable(id);
            }
            // Clear all caches so refresh will re-fetch
            hasCachedQuestions = false;
            cachedSectionQuestions = {};
            cachedFinalQuestions = null;
            if (currentTemplateId) {
                localStorage.removeItem(`examQuestionIds_${currentTemplateId}`);
            }
            saveViewState();
        }

        function updateSectionCount(id, value) {
            const section = examSections.find(s => s.id === id);
            if (section) section.count = value ? parseInt(value) : null; // null = use all
            // Clear all caches so refresh will re-fetch
            hasCachedQuestions = false;
            cachedSectionQuestions = {};
            cachedFinalQuestions = null;
            if (currentTemplateId) {
                localStorage.removeItem(`examQuestionIds_${currentTemplateId}`);
            }
            updateExamStats();
            saveViewState();
        }

        function updateSectionConstraint(id, field, value) {
            const section = examSections.find(s => s.id === id);
            if (section) {
                section[field] = value ? parseInt(value) : null;
            }
            // Clear all caches so refresh will re-fetch
            hasCachedQuestions = false;
            cachedSectionQuestions = {};
            cachedFinalQuestions = null;
            if (currentTemplateId) {
                localStorage.removeItem(`examQuestionIds_${currentTemplateId}`);
            }
            saveViewState();
        }

        async function updateSectionAvailable(sectionId) {
            const section = examSections.find(s => s.id === sectionId);
            if (!section) return;

            const params = new URLSearchParams();
            if (section.course) params.append('course', section.course);
            if (section.type) params.append('type', section.type);
            section.tags.forEach(t => params.append('tags', t));

            const data = await api(`questions/?${params.toString()}&page_size=1`);
            const count = data.count || 0;

            const el = document.getElementById(`section-available-${sectionId}`);
            if (el) {
                el.textContent = count;
                el.className = `px-2 py-1.5 text-sm font-medium ${count >= section.count ? 'text-emerald-600' : 'text-amber-600'}`;
            }
        }

        async function refreshExamPreview(forceRefresh = false) {
            try {
            const previewContainer = document.getElementById('exam-preview');
            if (!examSections.length) {
                previewContainer.innerHTML = '<div class="text-center py-6 text-gray-400 text-sm">Add sections first</div>';
                return;
            }

            // Try to restore from localStorage on page reload
            if (!forceRefresh && !hasCachedQuestions && currentTemplateId) {
                const savedIds = localStorage.getItem(`examQuestionIds_${currentTemplateId}`);
                if (savedIds) {
                    try {
                        const questionIds = JSON.parse(savedIds);
                        // Fetch these specific questions
                        const questionsData = await Promise.all(
                            questionIds.map(id => api(`questions/${id}/`).catch(() => null))
                        );
                        const restoredQuestions = questionsData.filter(q => q !== null);

                        if (restoredQuestions.length > 0) {
                            // Restore section info
                            restoredQuestions.forEach(q => {
                                const section = examSections.find(s =>
                                    q.tags?.some(t => s.tags.includes(t.name))
                                );
                                q._section = section?.name || 'Unknown';
                            });

                            cachedFinalQuestions = restoredQuestions;
                            hasCachedQuestions = true;
                        }
                    } catch (e) {
                        console.error('Error restoring questions from localStorage:', e);
                    }
                }
            }

            // Use cached final result if available (simple flag - reset when template loads)
            if (!forceRefresh && hasCachedQuestions && cachedFinalQuestions) {
                // Use cached questions - just re-render
                const allQuestions = cachedFinalQuestions;
                currentExamQuestions = allQuestions;
                selectedQuestions.clear();
                allQuestions.forEach(q => selectedQuestions.add(q.id));

                previewContainer.innerHTML = allQuestions.map((q, idx) => `
                    <div class="exam-question-preview p-3 rounded-lg bg-gray-50 dark:bg-slate-800/50 border border-gray-100 dark:border-slate-700" data-question-id="${q.id}">
                        <div class="flex items-start gap-3">
                            <span class="text-xs font-medium text-gray-400 mt-0.5">${idx + 1}</span>
                            <div class="flex-1 min-w-0">
                                <div class="flex items-center gap-2 mb-1">
                                    <span class="badge ${getTypeBadgeClass(q.question_type)} text-xs">${formatType(q.question_type)}</span>
                                    <span class="text-xs text-emerald-600 dark:text-emerald-400">${escapeHtml(q._section)}</span>
                                    <span class="exam-points-display text-xs text-gray-400 cursor-pointer hover:text-sky-500 hover:underline"
                                          onclick="editExamQuestionPoints(${q.id}, ${q.points})" title="Click to edit points">${q.points} pts</span>
                                    <div class="ml-auto flex items-center gap-1">
                                        <button onclick="editQuestionFromExam(${q.id})" class="p-1 rounded hover:bg-gray-200 dark:hover:bg-slate-600" title="Edit question">
                                            <i data-lucide="pencil" class="w-3.5 h-3.5 text-gray-400 hover:text-sky-500"></i>
                                        </button>
                                        <button onclick="removeQuestionFromExam(${q.id})" class="p-1 rounded hover:bg-gray-200 dark:hover:bg-slate-600" title="Remove from exam">
                                            <i data-lucide="x" class="w-3.5 h-3.5 text-gray-400 hover:text-red-500"></i>
                                        </button>
                                    </div>
                                </div>
                                <p class="text-sm text-gray-700 dark:text-slate-300 line-clamp-2">${escapeHtml(q.text)}</p>
                            </div>
                        </div>
                        ${q.question_type === 'longAnswer' ? getAnswerSpaceBox(q) : ''}
                        ${q.question_type === 'shortAnswer' ? getAnswerLineBox(q) : ''}
                    </div>
                `).join('');

                initAnswerSpaceDrag();
                initAnswerLineDrag();
                updateExamStats();
                lucide.createIcons();
                return;
            }

            // If forceRefresh (Shuffle), clear saved question IDs
            if (forceRefresh && currentTemplateId) {
                localStorage.removeItem(`examQuestionIds_${currentTemplateId}`);
            }

            previewContainer.innerHTML = '<div class="text-center py-6"><i data-lucide="loader-2" class="w-6 h-6 animate-spin mx-auto text-sky-500"></i></div>';
            lucide.createIcons();

            selectedQuestions.clear();
            questionOverrides = {}; // Reset overrides when refreshing
            let allQuestions = [];

            // Helper to create a cache key for a section
            function getSectionCacheKey(section) {
                return JSON.stringify({
                    course: section.course,
                    tags: section.tags.slice().sort(),
                    type: section.type,
                    count: section.count,
                    maxPoints: section.maxPoints,
                    maxMCPoints: section.maxMCPoints,
                    maxTFPoints: section.maxTFPoints,
                    maxShortPoints: section.maxShortPoints,
                    maxLongPoints: section.maxLongPoints
                });
            }

            for (const section of examSections) {
                const cacheKey = getSectionCacheKey(section);

                // Check if we have cached questions for this section config
                if (!forceRefresh && cachedSectionQuestions[cacheKey]) {
                    const sectionQuestions = cachedSectionQuestions[cacheKey];
                    sectionQuestions.forEach(q => {
                        q._section = section.name;
                        selectedQuestions.add(q.id);
                    });
                    allQuestions = allQuestions.concat(sectionQuestions);
                    continue;
                }

                const params = new URLSearchParams();
                if (section.course) params.append('course', section.course);
                if (section.type) params.append('type', section.type);
                section.tags.forEach(t => params.append('tags', t));
                params.append('page_size', 200); // Fetch more to allow for constraint filtering

                const data = await api(`questions/?${params.toString()}`);
                let questions = data.results || data || [];

                // Shuffle questions for random selection
                questions = questions.sort(() => Math.random() - 0.5);

                // Apply point constraints per question type
                let sectionQuestions = [];
                const typePoints = {
                    multipleChoice: 0,
                    trueFalse: 0,
                    shortAnswer: 0,
                    longAnswer: 0
                };
                let totalPoints = 0;
                const maxTotal = section.maxPoints || Infinity;
                const maxByType = {
                    multipleChoice: section.maxMCPoints || Infinity,
                    trueFalse: section.maxTFPoints || Infinity,
                    shortAnswer: section.maxShortPoints || Infinity,
                    longAnswer: section.maxLongPoints || Infinity
                };

                // Check if we have any constraints
                const hasConstraints = section.maxPoints || section.maxMCPoints ||
                    section.maxTFPoints || section.maxShortPoints || section.maxLongPoints;

                if (hasConstraints) {
                    // Use constraint-based selection
                    for (const q of questions) {
                        const pts = parseFloat(q.points) || 0;
                        const qType = q.question_type;
                        const typeMax = maxByType[qType] || Infinity;

                        // Check if adding this question would exceed limits
                        if (typePoints[qType] + pts <= typeMax && totalPoints + pts <= maxTotal) {
                            sectionQuestions.push(q);
                            typePoints[qType] = (typePoints[qType] || 0) + pts;
                            totalPoints += pts;
                        }
                    }
                } else {
                    // Simple count-based selection (or all if count is null)
                    sectionQuestions = section.count ? questions.slice(0, section.count) : questions;
                }

                // Cache the selected questions for this section config
                cachedSectionQuestions[cacheKey] = sectionQuestions.map(q => ({...q}));

                sectionQuestions.forEach(q => {
                    q._section = section.name;
                    selectedQuestions.add(q.id);
                });
                allQuestions = allQuestions.concat(sectionQuestions);
            }

            // Apply template-level constraints (across all sections)
            const examMaxPoints = parseFloat(document.getElementById('exam-max-points')?.value) || Infinity;
            const examMaxMC = parseFloat(document.getElementById('exam-max-mc-points')?.value) || Infinity;
            const examMaxTF = parseFloat(document.getElementById('exam-max-tf-points')?.value) || Infinity;
            const examMaxShort = parseFloat(document.getElementById('exam-max-short-points')?.value) || Infinity;
            const examMaxLong = parseFloat(document.getElementById('exam-max-long-points')?.value) || Infinity;

            const hasExamConstraints = examMaxPoints !== Infinity || examMaxMC !== Infinity ||
                examMaxTF !== Infinity || examMaxShort !== Infinity || examMaxLong !== Infinity;

            if (hasExamConstraints) {
                const examTypePoints = { multipleChoice: 0, trueFalse: 0, shortAnswer: 0, longAnswer: 0 };
                let examTotalPoints = 0;
                const filteredQuestions = [];

                for (const q of allQuestions) {
                    const pts = parseFloat(q.points) || 0;
                    const qType = q.question_type;
                    const typeMax = {
                        multipleChoice: examMaxMC,
                        trueFalse: examMaxTF,
                        shortAnswer: examMaxShort,
                        longAnswer: examMaxLong
                    }[qType] || Infinity;

                    if (examTypePoints[qType] + pts <= typeMax && examTotalPoints + pts <= examMaxPoints) {
                        filteredQuestions.push(q);
                        examTypePoints[qType] = (examTypePoints[qType] || 0) + pts;
                        examTotalPoints += pts;
                    } else {
                        selectedQuestions.delete(q.id);
                    }
                }
                allQuestions = filteredQuestions;
            }

            // Store for stats calculation and cache for future refreshes
            currentExamQuestions = allQuestions;
            cachedFinalQuestions = allQuestions.map(q => ({...q})); // Deep copy
            hasCachedQuestions = true;

            // Persist selected question IDs to localStorage for browser reload
            if (currentTemplateId) {
                localStorage.setItem(`examQuestionIds_${currentTemplateId}`, JSON.stringify(allQuestions.map(q => q.id)));
            }

            if (!allQuestions.length) {
                previewContainer.innerHTML = '<div class="text-center py-6 text-gray-400 text-sm">No questions match your criteria</div>';
                updateExamStats();
                return;
            }

            previewContainer.innerHTML = allQuestions.map((q, idx) => `
                <div class="exam-question-preview p-3 rounded-lg bg-gray-50 dark:bg-slate-800/50 border border-gray-100 dark:border-slate-700" data-question-id="${q.id}">
                    <div class="flex items-start gap-3">
                        <span class="text-xs font-medium text-gray-400 mt-0.5">${idx + 1}</span>
                        <div class="flex-1 min-w-0">
                            <div class="flex items-center gap-2 mb-1">
                                <span class="badge ${getTypeBadgeClass(q.question_type)} text-xs">${formatType(q.question_type)}</span>
                                <span class="text-xs text-emerald-600 dark:text-emerald-400">${escapeHtml(q._section)}</span>
                                <span class="exam-points-display text-xs text-gray-400 cursor-pointer hover:text-sky-500 hover:underline"
                                      onclick="editExamQuestionPoints(${q.id}, ${q.points})" title="Click to edit points">${q.points} pts</span>
                                <div class="ml-auto flex items-center gap-1">
                                    <button onclick="editQuestionFromExam(${q.id})" class="p-1 rounded hover:bg-gray-200 dark:hover:bg-slate-600" title="Edit question">
                                        <i data-lucide="pencil" class="w-3.5 h-3.5 text-gray-400 hover:text-sky-500"></i>
                                    </button>
                                    <button onclick="removeQuestionFromExam(${q.id})" class="p-1 rounded hover:bg-gray-200 dark:hover:bg-slate-600" title="Remove from exam">
                                        <i data-lucide="x" class="w-3.5 h-3.5 text-gray-400 hover:text-red-500"></i>
                                    </button>
                                </div>
                            </div>
                            <p class="text-sm text-gray-700 dark:text-slate-300 line-clamp-2">${escapeHtml(q.text)}</p>
                        </div>
                    </div>
                    ${q.question_type === 'longAnswer' ? getAnswerSpaceBox(q) : ''}
                    ${q.question_type === 'shortAnswer' ? getAnswerLineBox(q) : ''}
                </div>
            `).join('');

            // Initialize drag handlers for answer space boxes and lines
            initAnswerSpaceDrag();
            initAnswerLineDrag();
            updateExamStats();
            lucide.createIcons();

            // If multiple versions selected, show version tabs with per-version previews
            const numVersions = parseInt(document.getElementById('exam-versions')?.value) || 1;
            if (numVersions > 1) {
                await refreshMultiVersionPreview();
            } else {
                document.getElementById('version-tabs').classList.add('hidden');
                versionPreviewData = null;
            }
            } catch (err) {
                console.error('Error in refreshExamPreview:', err);
                showToast('Error refreshing preview: ' + err.message, 'error');
            }
        }

        // Multi-version preview functions
        async function fetchMultiVersionPreview(questionIds, numVersions) {
            const response = await api('exams/preview/versions/', 'POST', {
                question_ids: questionIds,
                versions: numVersions
            });
            return response;
        }

        function renderVersionTabs(versions) {
            const tabsContainer = document.getElementById('version-tabs');
            const tabsList = document.getElementById('version-tabs-list');

            if (versions.length <= 1) {
                tabsContainer.classList.add('hidden');
                return;
            }

            tabsContainer.classList.remove('hidden');
            tabsList.innerHTML = versions.map(v => `
                <button onclick="switchPreviewVersion('${v.version}')"
                    class="version-tab px-4 py-2 text-sm font-medium border-b-2 transition-colors
                        ${v.version === currentPreviewVersion
                            ? 'border-sky-500 text-sky-600 dark:text-sky-400'
                            : 'border-transparent text-gray-500 hover:text-gray-700 dark:text-slate-400 hover:border-gray-300'}"
                    data-version="${v.version}">
                    Version ${v.version}
                    <span class="ml-1 text-xs ${v.total_points !== versions[0].total_points ? 'text-amber-500' : 'text-gray-400'}">
                        (${v.total_points} pts)
                    </span>
                </button>
            `).join('');
        }

        function switchPreviewVersion(version) {
            currentPreviewVersion = version;
            if (versionPreviewData) {
                renderVersionTabs(versionPreviewData.versions);
                const versionData = versionPreviewData.versions.find(v => v.version === version);
                if (versionData) {
                    renderVersionPreview(versionData);
                    updateVersionStats(versionData);
                }
            }
        }

        function updateVersionStats(versionData) {
            const statsContainer = document.getElementById('version-stats');
            if (!statsContainer) return;

            const typeLabels = {
                multipleChoice: 'MC',
                trueFalse: 'T/F',
                shortAnswer: 'Short',
                longAnswer: 'Long'
            };

            const typeStats = Object.entries(versionData.by_type)
                .map(([type, data]) => `${typeLabels[type] || type}: ${data.count} (${data.points} pts)`)
                .join(' • ');

            statsContainer.innerHTML = `
                <span class="font-medium">${versionData.question_count} questions</span> •
                <span class="font-medium text-emerald-600 dark:text-emerald-400">${versionData.total_points} total points</span>
                ${typeStats ? ` • ${typeStats}` : ''}
                ${versionPreviewData.has_variants ? '<span class="ml-2 text-amber-500"><i data-lucide="git-branch" class="w-3 h-3 inline"></i> Has variants</span>' : ''}
            `;
            lucide.createIcons();
        }

        function renderVersionPreview(versionData) {
            const previewContainer = document.getElementById('exam-preview');
            const questions = versionData.questions;

            if (!questions.length) {
                previewContainer.innerHTML = '<div class="text-center py-6 text-gray-400 text-sm">No questions in this version</div>';
                return;
            }

            previewContainer.innerHTML = questions.map((q, idx) => `
                <div class="exam-question-preview p-3 rounded-lg bg-gray-50 dark:bg-slate-800/50 border border-gray-100 dark:border-slate-700" data-question-id="${q.id}">
                    <div class="flex items-start gap-3">
                        <span class="text-xs font-medium text-gray-400 mt-0.5">${idx + 1}</span>
                        <div class="flex-1 min-w-0">
                            <div class="flex items-center gap-2 mb-1 flex-wrap">
                                <span class="badge ${getTypeBadgeClass(q.type)} text-xs">${formatType(q.type)}</span>
                                ${q.block_name ? `<span class="text-xs bg-amber-100 dark:bg-amber-900/30 text-amber-700 dark:text-amber-300 px-1.5 py-0.5 rounded" title="Question variant from block: ${escapeHtml(q.block_name)}">
                                    <i data-lucide="git-branch" class="w-3 h-3 inline"></i> ${escapeHtml(q.block_name)} v${q.variant_number}
                                </span>` : ''}
                                <span class="exam-points-display text-xs text-gray-400">${q.points} pts</span>
                                ${q.tags && q.tags.length ? `<span class="text-xs text-gray-400">${q.tags.slice(0, 2).join(', ')}${q.tags.length > 2 ? '...' : ''}</span>` : ''}
                            </div>
                            <p class="text-sm text-gray-700 dark:text-slate-300 line-clamp-3">${escapeHtml(q.text)}</p>
                        </div>
                    </div>
                </div>
            `).join('');

            lucide.createIcons();
        }

        async function refreshMultiVersionPreview() {
            const numVersions = parseInt(document.getElementById('exam-versions')?.value) || 1;
            if (numVersions <= 1 || !selectedQuestions.size) {
                // Single version - use existing preview
                document.getElementById('version-tabs').classList.add('hidden');
                return;
            }

            const previewContainer = document.getElementById('exam-preview');
            previewContainer.innerHTML = '<div class="text-center py-6"><i data-lucide="loader-2" class="w-6 h-6 animate-spin mx-auto text-sky-500"></i><p class="mt-2 text-sm text-gray-400">Generating version previews...</p></div>';
            lucide.createIcons();

            try {
                versionPreviewData = await fetchMultiVersionPreview(Array.from(selectedQuestions), numVersions);
                currentPreviewVersion = 'A';
                renderVersionTabs(versionPreviewData.versions);
                const firstVersion = versionPreviewData.versions[0];
                if (firstVersion) {
                    renderVersionPreview(firstVersion);
                    updateVersionStats(firstVersion);
                }
            } catch (err) {
                console.error('Error fetching multi-version preview:', err);
                showToast('Error generating version previews', 'error');
            }
        }

        // Convert inches to pixels for display (using ~50px per inch for visual representation)
        const PIXELS_PER_INCH = 50;
        const SNAP_SIZES_VERTICAL = [1, 1.5, 2, 2.5, 3, 4, 5, 6]; // Common sizes for solution space
        const SNAP_SIZES_HORIZONTAL = [0.5, 1, 1.5, 2, 2.5, 3, 3.5, 4, 4.5, 5]; // Common sizes for line length

        function parseInches(value) {
            if (!value) return 1.5; // default
            if (value === '\\stretch{1}') return 4; // treat fill as 4 inches for display
            const match = value.match(/^([\d.]+)in$/);
            return match ? parseFloat(match[1]) : 1.5;
        }

        function getAnswerSpaceBox(q) {
            const defaultSpace = document.getElementById('exam-solution-space')?.value || '1.5in';
            const savedSpace = (q.answer_data || {}).solutionSpace || '';
            const currentSpace = savedSpace || defaultSpace;
            const inches = parseInches(currentSpace);
            const height = Math.round(inches * PIXELS_PER_INCH);

            return `
                <div class="answer-space-container mt-2 ml-6">
                    <div class="answer-space-box"
                         data-question-id="${q.id}"
                         data-inches="${inches}"
                         style="height: ${height}px;">
                        <div class="answer-space-content">
                            <span class="answer-space-label">Answer Space</span>
                        </div>
                        <div class="answer-space-handle">
                            <span class="answer-space-size">${inches} in</span>
                            <i data-lucide="grip-horizontal" class="w-4 h-4"></i>
                        </div>
                    </div>
                </div>`;
        }

        function initAnswerSpaceDrag() {
            document.querySelectorAll('.answer-space-box').forEach(box => {
                const handle = box.querySelector('.answer-space-handle');
                let startY, startHeight, isDragging = false;

                handle.addEventListener('mousedown', (e) => {
                    e.preventDefault();
                    isDragging = true;
                    startY = e.clientY;
                    startHeight = box.offsetHeight;
                    document.body.style.cursor = 'ns-resize';
                    document.body.style.userSelect = 'none';
                });

                document.addEventListener('mousemove', (e) => {
                    if (!isDragging) return;
                    const deltaY = e.clientY - startY;
                    const newHeight = Math.max(PIXELS_PER_INCH * 0.5, startHeight + deltaY); // min 0.5 inch
                    box.style.height = newHeight + 'px';

                    // Calculate inches and snap to nearest size
                    let inches = newHeight / PIXELS_PER_INCH;
                    const snapped = SNAP_SIZES_VERTICAL.reduce((prev, curr) =>
                        Math.abs(curr - inches) < Math.abs(prev - inches) ? curr : prev
                    );

                    // Show snapped value if close enough
                    const snapThreshold = 0.15;
                    const displayInches = Math.abs(snapped - inches) < snapThreshold ? snapped : Math.round(inches * 4) / 4;

                    box.dataset.inches = displayInches;
                    box.querySelector('.answer-space-size').textContent = displayInches + ' in';
                });

                document.addEventListener('mouseup', () => {
                    if (!isDragging) return;
                    isDragging = false;
                    document.body.style.cursor = '';
                    document.body.style.userSelect = '';

                    // Snap to final size
                    const inches = parseFloat(box.dataset.inches);
                    const snapped = SNAP_SIZES_VERTICAL.reduce((prev, curr) =>
                        Math.abs(curr - inches) < Math.abs(prev - inches) ? curr : prev
                    );

                    box.style.height = (snapped * PIXELS_PER_INCH) + 'px';
                    box.dataset.inches = snapped;
                    box.querySelector('.answer-space-size').textContent = snapped + ' in';

                    // Update override
                    const questionId = box.dataset.questionId;
                    setQuestionOverride(questionId, 'solutionSpace', snapped + 'in');
                });
            });

            // Re-initialize lucide icons for the grip handles
            lucide.createIcons();
        }

        function getAnswerLineBox(q) {
            const defaultLength = document.getElementById('exam-line-length')?.value || '3in';
            const savedLength = (q.answer_data || {}).lineLength || '';
            const currentLength = savedLength || defaultLength;
            const inches = parseInches(currentLength);
            const width = Math.round(inches * PIXELS_PER_INCH);
            const isFullWidth = currentLength === '\\linewidth';

            return `
                <div class="answer-line-container mt-2 ml-6">
                    <div class="answer-line-box"
                         data-question-id="${q.id}"
                         data-inches="${isFullWidth ? 'full' : inches}"
                         style="width: ${isFullWidth ? '100%' : width + 'px'};">
                        <div class="answer-line"></div>
                        <div class="answer-line-handle">
                            <i data-lucide="grip-vertical" class="w-3 h-3"></i>
                            <span class="answer-line-size">${isFullWidth ? 'Full' : inches + ' in'}</span>
                        </div>
                    </div>
                </div>`;
        }

        function initAnswerLineDrag() {
            document.querySelectorAll('.answer-line-box').forEach(box => {
                const handle = box.querySelector('.answer-line-handle');
                const container = box.closest('.answer-line-container');
                let startX, startWidth, isDragging = false;
                const maxWidth = container.offsetWidth - 20; // Leave room for handle

                handle.addEventListener('mousedown', (e) => {
                    e.preventDefault();
                    isDragging = true;
                    startX = e.clientX;
                    startWidth = box.offsetWidth;
                    document.body.style.cursor = 'ew-resize';
                    document.body.style.userSelect = 'none';
                });

                document.addEventListener('mousemove', (e) => {
                    if (!isDragging) return;
                    // Inverted: drag LEFT to make wider (negative deltaX = wider)
                    const deltaX = startX - e.clientX;
                    const newWidth = Math.max(PIXELS_PER_INCH, Math.min(maxWidth, startWidth + deltaX));
                    box.style.width = newWidth + 'px';

                    // Calculate inches
                    let inches = newWidth / PIXELS_PER_INCH;

                    // Check if close to full width
                    const isFullWidth = newWidth >= maxWidth - 10;

                    if (isFullWidth) {
                        box.dataset.inches = 'full';
                        box.querySelector('.answer-line-size').textContent = 'Full';
                    } else {
                        const snapped = SNAP_SIZES_HORIZONTAL.reduce((prev, curr) =>
                            Math.abs(curr - inches) < Math.abs(prev - inches) ? curr : prev
                        );
                        const snapThreshold = 0.2;
                        const displayInches = Math.abs(snapped - inches) < snapThreshold ? snapped : Math.round(inches * 2) / 2;
                        box.dataset.inches = displayInches;
                        box.querySelector('.answer-line-size').textContent = displayInches + ' in';
                    }
                });

                document.addEventListener('mouseup', () => {
                    if (!isDragging) return;
                    isDragging = false;
                    document.body.style.cursor = '';
                    document.body.style.userSelect = '';

                    const questionId = box.dataset.questionId;
                    const inchesValue = box.dataset.inches;

                    if (inchesValue === 'full') {
                        box.style.width = '100%';
                        setQuestionOverride(questionId, 'lineLength', '\\linewidth');
                    } else {
                        const inches = parseFloat(inchesValue);
                        const snapped = SNAP_SIZES_HORIZONTAL.reduce((prev, curr) =>
                            Math.abs(curr - inches) < Math.abs(prev - inches) ? curr : prev
                        );
                        box.style.width = (snapped * PIXELS_PER_INCH) + 'px';
                        box.dataset.inches = snapped;
                        box.querySelector('.answer-line-size').textContent = snapped + ' in';
                        setQuestionOverride(questionId, 'lineLength', snapped + 'in');
                    }
                });
            });

            // Re-initialize lucide icons
            lucide.createIcons();
        }

        function setQuestionOverride(questionId, field, value) {
            if (!questionOverrides[questionId]) {
                questionOverrides[questionId] = {};
            }
            if (value) {
                questionOverrides[questionId][field] = value;
            } else {
                delete questionOverrides[questionId][field];
                if (Object.keys(questionOverrides[questionId]).length === 0) {
                    delete questionOverrides[questionId];
                }
            }
            saveViewState();
        }

        // Edit question points inline from exam builder
        function editExamQuestionPoints(questionId, currentPoints) {
            const newPoints = prompt('Enter new points value:', currentPoints);
            if (newPoints === null) return; // Cancelled

            const points = parseFloat(newPoints);
            if (isNaN(points) || points < 0) {
                alert('Please enter a valid positive number');
                return;
            }

            // Update via API
            api(`questions/${questionId}/`, 'PATCH', { points: points })
                .then(() => {
                    // Update the display
                    const container = document.querySelector(`.exam-question-preview[data-question-id="${questionId}"]`);
                    if (container) {
                        const pointsSpan = container.querySelector('.exam-points-display');
                        if (pointsSpan) {
                            pointsSpan.textContent = points + ' pts';
                            pointsSpan.setAttribute('onclick', `editExamQuestionPoints(${questionId}, ${points})`);
                        }
                    }
                    updateExamStats();
                })
                .catch(err => alert('Error updating points: ' + err.message));
        }

        // Open question modal from exam builder
        async function editQuestionFromExam(questionId) {
            await openQuestion(questionId);
        }

        // Remove a question from the exam preview
        function removeQuestionFromExam(questionId) {
            selectedQuestions.delete(questionId);
            delete questionOverrides[questionId];

            // Remove from currentExamQuestions
            currentExamQuestions = currentExamQuestions.filter(q => q.id !== questionId);

            // Remove from DOM
            const container = document.querySelector(`.exam-question-preview[data-question-id="${questionId}"]`);
            if (container) {
                container.remove();
            }

            // Re-number remaining questions
            document.querySelectorAll('.exam-question-preview').forEach((el, idx) => {
                const numSpan = el.querySelector('.text-xs.font-medium.text-gray-400');
                if (numSpan) numSpan.textContent = idx + 1;
            });

            updateExamStats();
            saveViewState();
        }

        async function generateExam(format) {
            if (!selectedQuestions.size) return alert('Please select at least one question');
            const numVersions = parseInt(document.getElementById('exam-versions')?.value || '1');
            const data = {
                question_ids: Array.from(selectedQuestions),
                title: document.getElementById('exam-title').value,
                course: document.getElementById('exam-course').value,
                instructor: document.getElementById('exam-instructor').value,
                term: document.getElementById('exam-term').value,
                instructions: document.getElementById('exam-instructions').value,
                shuffle: true, // Always shuffle within sections
                include_answers: document.getElementById('exam-answers').checked,
                is_quiz: document.getElementById('exam-quiz-mode')?.checked || false,
                include_id: document.getElementById('exam-include-id')?.checked || false,
                split_mc: document.getElementById('exam-split-mc')?.checked || false,
                line_length: document.getElementById('exam-line-length')?.value || '3in',
                solution_space: document.getElementById('exam-solution-space')?.value || '1.5in',
                question_overrides: questionOverrides,
                versions: numVersions,
                format: format
            };

            // Show progress indicator
            const progressDiv = document.getElementById('generation-progress');
            const statusSpan = document.getElementById('generation-status');
            const btnHtml = document.getElementById('btn-generate-html');
            const btnPdf = document.getElementById('btn-generate-pdf');

            function showProgress(message) {
                if (progressDiv) progressDiv.classList.remove('hidden');
                if (statusSpan) statusSpan.textContent = message;
                if (btnHtml) btnHtml.disabled = true;
                if (btnPdf) btnPdf.disabled = true;
            }

            function hideProgress() {
                if (progressDiv) progressDiv.classList.add('hidden');
                if (btnHtml) btnHtml.disabled = false;
                if (btnPdf) btnPdf.disabled = false;
            }

            try {
                if (format === 'html') {
                    showProgress('Generating HTML preview...');
                    const res = await api('exams/generate/', 'POST', data);
                    hideProgress();
                    if (res.content) {
                        const frame = document.getElementById('preview-frame');
                        frame.srcdoc = res.content;
                        showModal('preview-modal');
                    }
                } else if (format === 'pdf') {
                    // Show appropriate message based on number of versions
                    if (numVersions > 1) {
                        showProgress(`Generating ${numVersions} exam versions... This may take a minute.`);
                    } else {
                        showProgress('Generating PDF...');
                    }

                    // For PDF, we need to handle the file download differently
                    const headers = { 'Content-Type': 'application/json' };
                    // Include CSRF token for POST request
                    const csrfToken = getCookie('csrftoken');
                    if (csrfToken) {
                        headers['X-CSRFToken'] = csrfToken;
                    }
                    const response = await fetch('/api/exams/generate/', {
                        method: 'POST',
                        headers: headers,
                        credentials: 'same-origin',
                        body: JSON.stringify(data)
                    });
                    hideProgress();

                    if (response.ok) {
                        const blob = await response.blob();
                        const url = window.URL.createObjectURL(blob);
                        const a = document.createElement('a');
                        a.href = url;
                        // Filename: ZIP if multiple versions OR if include_answers (since we generate exam + key)
                        const includeAnswers = document.getElementById('exam-answers')?.checked;
                        let filename;
                        if (numVersions > 1) {
                            filename = `${data.title.replace(/\s+/g, '_')}_versions.zip`;
                        } else if (includeAnswers) {
                            filename = `${data.title.replace(/\s+/g, '_')}.zip`;
                        } else {
                            filename = `${data.title.replace(/\s+/g, '_')}.pdf`;
                        }
                        a.download = filename;
                        a.click();
                    } else {
                        const err = await response.json();
                        alert('PDF generation failed: ' + (err.error || 'Unknown error'));
                    }
                }
            } catch (error) {
                hideProgress();
                console.error('Generation error:', error);
                alert('Generation failed: ' + error.message);
            }
        }

        function printPreview() {
            document.getElementById('preview-frame').contentWindow.print();
        }

        function closePreviewModal() { hideModal('preview-modal'); }

        function toggleQuizModeOptions() {
            const quizMode = document.getElementById('exam-quiz-mode')?.checked;
            // When quiz mode is enabled, set the defaults for quiz mode
            if (quizMode) {
                const includeIdCheckbox = document.getElementById('exam-include-id');
                const splitMcCheckbox = document.getElementById('exam-split-mc');
                if (includeIdCheckbox) includeIdCheckbox.checked = true;
                if (splitMcCheckbox) splitMcCheckbox.checked = true;
            }
        }

        // AI Generation - Course/Tag Selectors
        async function loadAiBankSelector() {
            const courseSelect = document.getElementById('ai-course');
            const tagSelect = document.getElementById('ai-tag');

            // Make sure courses and banks are loaded
            if (!courses || courses.length === 0) {
                const data = await api('courses/');
                courses = data.results || data || [];
            }
            if (!banks || banks.length === 0) {
                const data = await api('banks/');
                banks = data.results || data || [];
            }

            // Populate courses
            courseSelect.innerHTML = '<option value="">Select a course...</option>';
            courses.forEach(c => {
                const opt = document.createElement('option');
                opt.value = c.code;
                opt.textContent = `${c.code} - ${c.name}`;
                courseSelect.appendChild(opt);
            });

            // Load tags when course changes
            courseSelect.onchange = async () => {
                const courseCode = courseSelect.value;
                tagSelect.innerHTML = '<option value="">No tag</option><option value="__new__">+ Create new tag...</option>';
                if (!courseCode) return;

                // Get tags for this course
                const data = await api(`tags/?course=${courseCode}`);
                const tags = data.results || data || [];
                tags.forEach(t => {
                    const opt = document.createElement('option');
                    opt.value = t.name;
                    opt.textContent = t.name;
                    opt.dataset.tagId = t.id;
                    tagSelect.insertBefore(opt, tagSelect.lastChild);
                });
            };

            // Handle new tag creation
            tagSelect.onchange = async () => {
                if (tagSelect.value === '__new__') {
                    const newTagName = prompt('Enter new tag name:');
                    if (newTagName && newTagName.trim()) {
                        const trimmedName = newTagName.trim();

                        // Check if tag already exists in dropdown
                        const existingOpt = Array.from(tagSelect.options).find(o => o.textContent === trimmedName);
                        if (existingOpt) {
                            tagSelect.value = existingOpt.value;
                            return;
                        }

                        // Check if tag already exists in allTags
                        let existingTag = allTags.find(t => t.name === trimmedName);
                        if (existingTag) {
                            const opt = document.createElement('option');
                            opt.value = trimmedName;
                            opt.textContent = trimmedName;
                            opt.dataset.tagId = existingTag.id;
                            tagSelect.insertBefore(opt, tagSelect.lastChild);
                            tagSelect.value = trimmedName;
                            return;
                        }

                        const res = await api('tags/', 'POST', { name: trimmedName });

                        // Check if response indicates error (400 returns error object)
                        if (res.name && res.name[0] && res.name[0].includes('already exists')) {
                            // Tag exists - reload tags and find it
                            await loadTags();
                            existingTag = allTags.find(t => t.name === trimmedName);
                            if (existingTag) {
                                const opt = document.createElement('option');
                                opt.value = trimmedName;
                                opt.textContent = trimmedName;
                                opt.dataset.tagId = existingTag.id;
                                tagSelect.insertBefore(opt, tagSelect.lastChild);
                                tagSelect.value = trimmedName;
                                return;
                            }
                            alert('Tag exists but could not be found. Please refresh the page.');
                            tagSelect.value = '';
                            return;
                        }

                        if (!res.id) {
                            console.error('[Tag] Unexpected response:', res);
                            alert('Failed to create tag');
                            tagSelect.value = '';
                            return;
                        }

                        // Success - add the new tag
                        const opt = document.createElement('option');
                        opt.value = trimmedName;
                        opt.textContent = trimmedName;
                        opt.dataset.tagId = res.id;
                        tagSelect.insertBefore(opt, tagSelect.lastChild);
                        tagSelect.value = trimmedName;
                        allTags.push({ id: res.id, name: res.name });
                    } else {
                        tagSelect.value = '';
                    }
                }
            };
        }

        // Get the tag ID from the selected option (either from data attribute or allTags lookup)
        function getSelectedTagId() {
            const tagSelect = document.getElementById('ai-tag');
            const tagName = tagSelect.value;
            if (!tagName || tagName === '__new__') return null;

            // First check if the option has a stored tagId
            const selectedOption = tagSelect.options[tagSelect.selectedIndex];
            if (selectedOption && selectedOption.dataset.tagId) {
                return parseInt(selectedOption.dataset.tagId);
            }

            // Fall back to looking up in allTags
            const tag = allTags.find(t => t.name === tagName);
            return tag ? tag.id : null;
        }

        // AI Generation - File Drop Handlers
        function handleDragOver(e) {
            e.preventDefault();
            e.currentTarget.classList.add('border-sky-400', 'bg-sky-50', 'dark:bg-sky-900/20');
        }

        function handleDragLeave(e) {
            e.preventDefault();
            e.currentTarget.classList.remove('border-sky-400', 'bg-sky-50', 'dark:bg-sky-900/20');
        }

        async function handleFileDrop(e) {
            e.preventDefault();
            e.currentTarget.classList.remove('border-sky-400', 'bg-sky-50', 'dark:bg-sky-900/20');

            const file = e.dataTransfer.files[0];
            if (!file) return;

            const validExts = ['.pptx', '.txt', '.md'];
            const ext = '.' + file.name.split('.').pop().toLowerCase();
            if (!validExts.includes(ext)) {
                alert('Unsupported file type. Please use .pptx, .txt, or .md files.');
                return;
            }

            const dropzone = document.getElementById('ai-dropzone');
            dropzone.innerHTML = '<i data-lucide="loader-2" class="w-8 h-8 mx-auto mb-2 text-sky-500 animate-spin"></i><p class="text-sm text-gray-500">Extracting content...</p>';
            lucide.createIcons();

            try {
                const formData = new FormData();
                formData.append('file', file);

                const res = await fetch('/api/ai/extract-file/', {
                    method: 'POST',
                    body: formData,
                    headers: {
                        'X-CSRFToken': getCookie('csrftoken') || ''
                    },
                    credentials: 'same-origin'
                });
                const data = await res.json();

                if (data.error) throw new Error(data.error);

                document.getElementById('ai-content').value = data.content;
                dropzone.innerHTML = `
                    <i data-lucide="check-circle" class="w-8 h-8 mx-auto mb-2 text-green-500"></i>
                    <p class="text-sm text-green-600">${escapeHtml(data.filename)} loaded (${data.chars} chars)</p>
                    <p class="text-xs text-gray-400 mt-1">Drop another file to replace</p>
                `;
                lucide.createIcons();
            } catch (err) {
                dropzone.innerHTML = `
                    <i data-lucide="alert-circle" class="w-8 h-8 mx-auto mb-2 text-red-500"></i>
                    <p class="text-sm text-red-600">${err.message}</p>
                    <p class="text-xs text-gray-400 mt-1">Try again or paste content manually</p>
                `;
                lucide.createIcons();
            }
        }

        async function generateQuestions() {
            const btn = document.getElementById('generate-btn');
            const content = document.getElementById('ai-content').value;
            if (!content) return alert('Please enter some content');

            btn.disabled = true;
            btn.innerHTML = '<i data-lucide="loader-2" class="w-5 h-5 animate-spin"></i> Generating...';
            lucide.createIcons();

            try {
                const res = await api('ai/generate/', 'POST', {
                    provider: document.getElementById('ai-provider').value,
                    content: content,
                    type: document.getElementById('ai-type').value,
                    difficulty: document.getElementById('ai-difficulty').value,
                    count: parseInt(document.getElementById('ai-count').value),
                });
                if (res.error) throw new Error(res.error);
                renderGeneratedQuestions(res.questions);
            } catch (e) {
                document.getElementById('generated-questions').innerHTML = `<div class="p-4 bg-red-50 text-red-600 rounded-lg">${e.message}</div>`;
            } finally {
                btn.disabled = false;
                btn.innerHTML = '<i data-lucide="sparkles" class="w-5 h-5"></i> Generate Questions';
                lucide.createIcons();
            }
        }

        function renderGeneratedQuestions(questions) {
            window.generatedQuestions = questions;
            const typeColors = {
                multipleChoice: 'bg-blue-100 text-blue-700 dark:bg-blue-900/50 dark:text-blue-300',
                trueFalse: 'bg-green-100 text-green-700 dark:bg-green-900/50 dark:text-green-300',
                shortAnswer: 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/50 dark:text-yellow-300',
                longAnswer: 'bg-orange-100 text-orange-700 dark:bg-orange-900/50 dark:text-orange-300'
            };

            const bankSelected = document.getElementById('ai-bank').value;
            const addAllBtn = bankSelected ? `
                <div class="mb-4 flex justify-end">
                    <button onclick="addAllGeneratedQuestions()" id="add-all-btn" class="btn-primary px-4 py-2 text-white rounded-lg text-sm font-medium flex items-center gap-2">
                        <i data-lucide="plus-circle" class="w-4 h-4"></i>
                        Add All ${questions.length} Questions
                    </button>
                </div>
            ` : '';

            document.getElementById('generated-questions').innerHTML = addAllBtn + questions.map((q, i) => {
                const qType = q.question_type || document.getElementById('ai-type').value;
                const typeLabel = formatType(qType);
                const typeClass = typeColors[qType] || 'bg-purple-100 text-purple-700';
                const answerPreview = q.answer_data.correct !== undefined
                    ? `Answer: ${q.answer_data.correct}`
                    : q.answer_data.solution
                        ? `Solution: ${q.answer_data.solution.substring(0, 100)}...`
                        : '';
                return `
                <div class="p-4 bg-gray-50 dark:bg-slate-700/50 rounded-xl border border-gray-100 dark:border-slate-600">
                    <div class="flex justify-between items-start mb-2">
                        <div class="flex gap-2">
                            <span class="badge bg-purple-100 text-purple-700 dark:bg-purple-900/50 dark:text-purple-300">Q${i + 1}</span>
                            <span class="badge ${typeClass}">${typeLabel}</span>
                        </div>
                        <button onclick="addGeneratedQuestion(${i})" class="text-sm text-sky-600 hover:text-sky-700 font-medium">+ Add to Bank</button>
                    </div>
                    <p class="text-gray-800 dark:text-slate-200 text-sm mb-2">${escapeHtml(q.text)}</p>
                    <div class="text-xs text-gray-500 dark:text-slate-400">${answerPreview}</div>
                </div>
            `}).join('');
            lucide.createIcons();
        }

        async function addAllGeneratedQuestions() {
            const courseCode = document.getElementById('ai-course').value;
            const tagName = document.getElementById('ai-tag').value;
            if (!courseCode) return alert('Please select a course first');

            // Find first bank for selected course
            const bank = banks.find(b => b.course_code === courseCode);
            if (!bank) return alert('No question bank found for this course. Please create one first.');

            const btn = document.getElementById('add-all-btn');
            btn.disabled = true;
            btn.innerHTML = '<i data-lucide="loader-2" class="w-4 h-4 animate-spin"></i> Adding...';
            lucide.createIcons();

            let added = 0;
            let failed = 0;

            for (const q of window.generatedQuestions) {
                try {
                    const qType = q.question_type || document.getElementById('ai-type').value;
                    const payload = {
                        question_bank: bank.id,
                        question_type: qType,
                        text: q.text,
                        answer_data: q.answer_data,
                        points: q.points || 2,
                        difficulty: q.difficulty || 'medium',
                        tag_ids: []
                    };

                    if (tagName && tagName !== '__new__') {
                        const tagId = getSelectedTagId();
                        console.log('[AddAll] Tag:', tagName, 'ID:', tagId);
                        if (tagId) payload.tag_ids = [tagId];
                    }

                    await api('questions/', 'POST', payload);
                    added++;
                } catch (e) {
                    console.error('[AddAll] Error adding question:', e);
                    failed++;
                }
            }

            btn.innerHTML = `<i data-lucide="check" class="w-4 h-4"></i> Added ${added} questions${failed ? ` (${failed} failed)` : ''}`;
            btn.classList.remove('btn-primary');
            btn.classList.add('bg-green-500');
            lucide.createIcons();
        }

        async function addGeneratedQuestion(i) {
            const q = window.generatedQuestions[i];
            const courseCode = document.getElementById('ai-course').value;
            const tagName = document.getElementById('ai-tag').value;

            // Find first bank for selected course
            const bank = banks.find(b => b.course_code === courseCode);

            // If course is selected (and has a bank), save directly
            if (courseCode && bank) {
                const qType = q.question_type || document.getElementById('ai-type').value;
                const btn = event.target;
                btn.disabled = true;
                btn.textContent = 'Adding...';

                try {
                    const payload = {
                        question_bank: bank.id,
                        question_type: qType,
                        text: q.text,
                        answer_data: q.answer_data,
                        points: q.points || 2,
                        difficulty: q.difficulty || 'medium',
                        tag_ids: []
                    };

                    // If tag selected, find its ID
                    if (tagName && tagName !== '__new__') {
                        const tagId = getSelectedTagId();
                        if (tagId) payload.tag_ids = [tagId];
                    }

                    await api('questions/', 'POST', payload);
                    btn.textContent = 'Added!';
                    btn.classList.remove('text-sky-600', 'hover:text-sky-700');
                    btn.classList.add('text-green-600');
                    setTimeout(() => {
                        btn.textContent = '+ Add to Bank';
                        btn.classList.add('text-sky-600', 'hover:text-sky-700');
                        btn.classList.remove('text-green-600');
                        btn.disabled = false;
                    }, 2000);
                } catch (e) {
                    btn.textContent = 'Error';
                    btn.classList.add('text-red-600');
                    setTimeout(() => {
                        btn.textContent = '+ Add to Bank';
                        btn.classList.remove('text-red-600');
                        btn.disabled = false;
                    }, 2000);
                }
            } else if (courseCode && !bank) {
                alert('No question bank found for this course. Please create one first.');
            } else {
                // Fall back to modal if no course selected
                const qType = q.question_type || document.getElementById('ai-type').value;
                document.getElementById('q-type').value = qType;
                document.getElementById('q-difficulty').value = q.difficulty || 'medium';
                document.getElementById('q-points').value = q.points || 2;
                if (editor) editor.setValue(q.text);
                updateAnswerFields(q.answer_data);
                editingQuestionId = null;
                document.getElementById('modal-title').textContent = 'Add Generated Question';
                document.getElementById('delete-btn').classList.add('hidden');
                showModal('question-modal');
            }
        }

        // Helpers
        function showModal(id) { document.getElementById(id).classList.remove('hidden'); document.getElementById(id).classList.add('flex'); }
        function hideModal(id) { document.getElementById(id).classList.add('hidden'); document.getElementById(id).classList.remove('flex'); }
        function closeModal() { hideModal('question-modal'); }

        function filterByCourse(code) {
            document.getElementById('filter-course').value = code;
            loadQuestions();
            showView('questions', { preventDefault: () => {}, target: document.querySelector('.sidebar-item') });
        }

        function formatType(t) {
            const m = { multipleChoice: 'MC', trueFalse: 'T/F', shortAnswer: 'Short', longAnswer: 'Long', matching: 'Match', multipart: 'Multi', easy: 'Long' };
            return m[t] || t;
        }

        function getTypeBadgeClass(t) {
            const c = { multipleChoice: 'bg-blue-100 text-blue-700', trueFalse: 'bg-purple-100 text-purple-700', shortAnswer: 'bg-emerald-100 text-emerald-700', longAnswer: 'bg-amber-100 text-amber-700', easy: 'bg-amber-100 text-amber-700' };
            return c[t] || 'bg-gray-100 text-gray-700';
        }

        function getDifficultyClass(d) {
            const c = { easy: 'bg-green-100 text-green-700', medium: 'bg-yellow-100 text-yellow-700', hard: 'bg-red-100 text-red-700' };
            return c[d] || 'bg-gray-100 text-gray-700';
        }

        function escapeHtml(t) { return t?.replace(/[&<>"']/g, m => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;' })[m]) || ''; }
        function debounce(fn, ms) { let t; return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); }; }

        // Simple Markdown to HTML for preview (basic support)
        function simpleMarkdown(text) {
            if (!text) return '';
            let html = escapeHtml(text);
            // Code blocks
            html = html.replace(/```(\w*)\n?([\s\S]*?)```/g, '<pre class="bg-gray-100 dark:bg-slate-800 p-2 rounded text-xs overflow-x-auto"><code>$2</code></pre>');
            // Inline code
            html = html.replace(/`([^`]+)`/g, '<code class="bg-gray-100 dark:bg-slate-700 px-1 rounded text-xs">$1</code>');
            // Images
            html = html.replace(/!\[([^\]]*)\]\(([^)]+)\)/g, '<img src="$2" alt="$1" class="max-w-full h-auto rounded my-2">');
            // Links
            html = html.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" class="text-sky-600 hover:underline" target="_blank">$1</a>');
            // Bold
            html = html.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
            // Italic
            html = html.replace(/\*([^*]+)\*/g, '<em>$1</em>');
            // Headers
            html = html.replace(/^### (.+)$/gm, '<h3 class="text-lg font-semibold mt-2">$1</h3>');
            html = html.replace(/^## (.+)$/gm, '<h2 class="text-xl font-semibold mt-2">$1</h2>');
            html = html.replace(/^# (.+)$/gm, '<h1 class="text-2xl font-bold mt-2">$1</h1>');
            // Lists
            html = html.replace(/^\* (.+)$/gm, '<li class="ml-4">$1</li>');
            html = html.replace(/^- (.+)$/gm, '<li class="ml-4">$1</li>');
            html = html.replace(/^(\d+)\. (.+)$/gm, '<li class="ml-4">$2</li>');
            // Line breaks
            html = html.replace(/\n/g, '<br>');
            return html;
        }

        // Image upload functions
        let questionImages = [];

        function triggerImageUpload() {
            document.getElementById('image-upload-input').click();
        }

        async function handleImageUpload(event) {
            const file = event.target.files[0];
            if (!file) return;

            const statusEl = document.getElementById('image-upload-status');
            statusEl.textContent = 'Uploading...';

            const formData = new FormData();
            formData.append('image', file);
            formData.append('alt_text', file.name.replace(/\.[^/.]+$/, ''));

            try {
                // Upload to the appropriate endpoint based on whether we're editing an existing question
                let endpoint = 'images/';
                if (editingQuestionId) {
                    endpoint = `questions/${editingQuestionId}/upload_image/`;
                }

                const response = await fetch(`/api/${endpoint}`, {
                    method: 'POST',
                    headers: {
                        'X-CSRFToken': getCookie('csrftoken')
                    },
                    credentials: 'same-origin',
                    body: formData
                });

                if (!response.ok) {
                    const err = await response.json();
                    throw new Error(err.error || 'Upload failed');
                }

                const image = await response.json();
                questionImages.push(image);
                updateImageGallery();

                // Insert markdown reference at cursor in editor
                if (editor) {
                    const position = editor.getPosition();
                    const markdownRef = `![${image.alt_text || 'image'}](${image.url})`;
                    editor.executeEdits('', [{
                        range: {
                            startLineNumber: position.lineNumber,
                            startColumn: position.column,
                            endLineNumber: position.lineNumber,
                            endColumn: position.column
                        },
                        text: markdownRef
                    }]);
                }

                statusEl.textContent = 'Uploaded!';
                setTimeout(() => { statusEl.textContent = ''; }, 2000);
            } catch (err) {
                console.error('Image upload failed:', err);
                statusEl.textContent = 'Upload failed: ' + err.message;
            }

            // Reset file input
            event.target.value = '';
        }

        function updateImageGallery() {
            const container = document.getElementById('question-images');
            const list = document.getElementById('question-images-list');

            if (questionImages.length === 0) {
                container.classList.add('hidden');
                return;
            }

            container.classList.remove('hidden');
            list.innerHTML = questionImages.map(img => `
                <div class="relative group">
                    <img src="${img.url}" alt="${escapeHtml(img.alt_text || '')}" class="w-16 h-16 object-cover rounded border border-gray-200 dark:border-slate-600">
                    <button onclick="insertImageMarkdown('${img.url}', '${escapeHtml(img.alt_text || 'image')}')"
                            class="absolute inset-0 bg-black/50 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center rounded"
                            title="Insert into text">
                        <i data-lucide="plus" class="w-4 h-4 text-white"></i>
                    </button>
                </div>
            `).join('');
            lucide.createIcons();
        }

        function insertImageMarkdown(url, alt) {
            if (editor) {
                const position = editor.getPosition();
                const markdownRef = `![${alt}](${url})`;
                editor.executeEdits('', [{
                    range: {
                        startLineNumber: position.lineNumber,
                        startColumn: position.column,
                        endLineNumber: position.lineNumber,
                        endColumn: position.column
                    },
                    text: markdownRef
                }]);
                editor.focus();
            }
        }

        async function loadQuestionImages(questionId) {
            questionImages = [];
            if (!questionId) {
                updateImageGallery();
                return;
            }

            try {
                const response = await api(`questions/${questionId}/images/`);
                questionImages = Array.isArray(response) ? response : [];
            } catch (err) {
                console.error('Failed to load question images:', err);
            }
            updateImageGallery();
        }

        // Live preview in editor
        let previewVisible = false;
        function togglePreview() {
            previewVisible = !previewVisible;
            const editorCol = document.getElementById('editor-col');
            const previewCol = document.getElementById('preview-col');
            const editorWrapper = document.getElementById('editor-wrapper');
            const toggleBtn = document.getElementById('preview-toggle');

            if (previewVisible) {
                editorWrapper.classList.remove('grid-cols-1');
                editorWrapper.classList.add('grid-cols-2');
                previewCol.classList.remove('hidden');
                toggleBtn.classList.add('bg-sky-100', 'text-sky-700');
                toggleBtn.classList.remove('bg-gray-100', 'text-gray-600');
                updatePreview();
                // Setup live preview updates
                if (editor) {
                    editor.onDidChangeModelContent(() => updatePreview());
                }
            } else {
                editorWrapper.classList.add('grid-cols-1');
                editorWrapper.classList.remove('grid-cols-2');
                previewCol.classList.add('hidden');
                toggleBtn.classList.remove('bg-sky-100', 'text-sky-700');
                toggleBtn.classList.add('bg-gray-100', 'text-gray-600');
            }
            lucide.createIcons();
        }

        function updatePreview() {
            const previewEl = document.getElementById('markdown-preview');
            if (!previewEl || !editor) return;
            const text = editor.getValue();
            previewEl.innerHTML = simpleMarkdown(text) || '<span class="text-gray-400">Preview will appear here...</span>';
        }

        // Bulk Operations
        function toggleBulkMode() {
            bulkMode = !bulkMode;
            bulkSelectedQuestions.clear();
            updateBulkUI();
            loadQuestions(currentPage);
        }

        function updateBulkUI() {
            const bulkBar = document.getElementById('bulk-action-bar');
            const bulkToggle = document.getElementById('bulk-toggle-btn');
            if (bulkMode) {
                bulkBar?.classList.remove('hidden');
                bulkToggle?.classList.add('bg-sky-100', 'dark:bg-sky-900/50');
            } else {
                bulkBar?.classList.add('hidden');
                bulkToggle?.classList.remove('bg-sky-100', 'dark:bg-sky-900/50');
            }
            updateBulkCount();
        }

        function updateBulkCount() {
            const countEl = document.getElementById('bulk-count');
            if (countEl) countEl.textContent = bulkSelectedQuestions.size;
        }

        function toggleBulkQuestion(id, checkbox) {
            if (checkbox.checked) {
                bulkSelectedQuestions.add(id);
            } else {
                bulkSelectedQuestions.delete(id);
            }
            updateBulkCount();
        }

        function selectAllVisible() {
            document.querySelectorAll('.bulk-checkbox').forEach(cb => {
                cb.checked = true;
                bulkSelectedQuestions.add(parseInt(cb.dataset.id));
            });
            updateBulkCount();
        }

        function deselectAll() {
            bulkSelectedQuestions.clear();
            document.querySelectorAll('.bulk-checkbox').forEach(cb => cb.checked = false);
            updateBulkCount();
        }

        async function bulkDelete() {
            if (!bulkSelectedQuestions.size) return alert('No questions selected');
            if (!confirm(`Delete ${bulkSelectedQuestions.size} questions? This cannot be undone.`)) return;

            for (const id of bulkSelectedQuestions) {
                await api(`questions/${id}/`, 'DELETE');
            }
            bulkSelectedQuestions.clear();
            updateBulkCount();
            loadQuestions(currentPage);
        }

        async function bulkTag() {
            if (!bulkSelectedQuestions.size) return alert('No questions selected');
            const tagName = prompt('Enter tag name to add to selected questions:');
            if (!tagName) return;

            // First ensure tag exists
            let tag = allTags.find(t => t.name.toLowerCase() === tagName.toLowerCase());
            if (!tag) {
                tag = await api('tags/', 'POST', { name: tagName, color: '#10b981' });
            }

            // Add tag to each question
            for (const id of bulkSelectedQuestions) {
                const q = await api(`questions/${id}/`);
                const existingTags = (q.tags || []).map(t => t.name);
                if (!existingTags.includes(tagName)) {
                    existingTags.push(tagName);
                    await api(`questions/${id}/`, 'PATCH', { tag_names: existingTags });
                }
            }

            loadTags();
            loadQuestions(currentPage);
            alert(`Added tag "${tagName}" to ${bulkSelectedQuestions.size} questions`);
        }

        async function bulkMove() {
            if (!bulkSelectedQuestions.size) return alert('No questions selected');

            // Show bank selector
            const bankOptions = banks.map(b => `${b.id}: ${b.course_code}/${b.name}`).join('\n');
            const bankId = prompt(`Enter bank ID to move questions to:\n\n${bankOptions}`);
            if (!bankId) return;

            for (const id of bulkSelectedQuestions) {
                await api(`questions/${id}/`, 'PATCH', { question_bank: parseInt(bankId) });
            }

            loadQuestions(currentPage);
            alert(`Moved ${bulkSelectedQuestions.size} questions to new bank`);
        }

        // Duplicate/clone question
        async function duplicateQuestion(id) {
            try {
                const cloned = await api(`questions/${id}/clone/`, 'POST');
                // Refresh the list and open the cloned question for editing
                await loadQuestions(currentPage);
                editQuestion(cloned.id);
                showNotification('Question cloned successfully', 'success');
            } catch (err) {
                console.error('Failed to clone question:', err);
                showNotification('Failed to clone question', 'error');
            }
        }

        // Simple notification helper
        function showNotification(message, type = 'info') {
            const colors = {
                success: 'bg-green-500',
                error: 'bg-red-500',
                info: 'bg-sky-500'
            };
            const notification = document.createElement('div');
            notification.className = `fixed bottom-4 right-4 ${colors[type]} text-white px-4 py-2 rounded-lg shadow-lg z-50 transition-opacity duration-300`;
            notification.textContent = message;
            document.body.appendChild(notification);
            setTimeout(() => {
                notification.style.opacity = '0';
                setTimeout(() => notification.remove(), 300);
            }, 3000);
        }

        // Trash functions
        async function loadTrash() {
            const container = document.getElementById('trash-list');
            container.innerHTML = '<div class="p-4 text-center text-gray-400 dark:text-slate-500">Loading...</div>';

            try {
                const data = await api('questions/?trash=true&page_size=100');
                const questions = data.results || data || [];

                // Update trash count in sidebar
                updateTrashCount(questions.length);

                if (questions.length === 0) {
                    container.innerHTML = `
                        <div class="p-12 text-center text-gray-400 dark:text-slate-500">
                            <i data-lucide="trash-2" class="w-12 h-12 mx-auto mb-3 opacity-50"></i>
                            <p>Trash is empty</p>
                        </div>
                    `;
                    lucide.createIcons();
                    return;
                }

                container.innerHTML = questions.map(q => `
                    <div class="p-4 hover:bg-gray-50 dark:hover:bg-slate-700/50 flex items-center gap-4 group">
                        <div class="flex-1 min-w-0">
                            <div class="flex items-center gap-2 mb-1">
                                <span class="text-xs font-medium px-2 py-0.5 rounded-full ${getTypeColor(q.question_type)}">${q.question_type_display || q.question_type}</span>
                                <span class="text-xs text-gray-400 dark:text-slate-500">${q.course_code || ''}</span>
                            </div>
                            <div class="text-sm text-gray-700 dark:text-slate-300 truncate">${q.text?.substring(0, 100) || 'No text'}...</div>
                            <div class="text-xs text-gray-400 dark:text-slate-500 mt-1">
                                Deleted ${q.deleted_at ? new Date(q.deleted_at).toLocaleDateString() : 'recently'}
                            </div>
                        </div>
                        <div class="flex items-center gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
                            <button onclick="restoreQuestion(${q.id})" class="px-3 py-1.5 text-sm bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400 rounded-lg hover:bg-green-200 dark:hover:bg-green-900/50 flex items-center gap-1">
                                <i data-lucide="undo-2" class="w-4 h-4"></i>
                                Restore
                            </button>
                            <button onclick="permanentDeleteQuestion(${q.id})" class="px-3 py-1.5 text-sm bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-400 rounded-lg hover:bg-red-200 dark:hover:bg-red-900/50 flex items-center gap-1">
                                <i data-lucide="trash-2" class="w-4 h-4"></i>
                                Delete
                            </button>
                        </div>
                    </div>
                `).join('');
                lucide.createIcons();
            } catch (err) {
                console.error('Failed to load trash:', err);
                container.innerHTML = '<div class="p-4 text-center text-red-500">Failed to load trash</div>';
            }
        }

        async function restoreQuestion(id) {
            try {
                await api(`questions/${id}/restore/`, 'POST');
                showNotification('Question restored successfully', 'success');
                loadTrash();
                loadQuestions(currentPage);
            } catch (err) {
                console.error('Failed to restore question:', err);
                showNotification('Failed to restore question', 'error');
            }
        }

        async function permanentDeleteQuestion(id) {
            if (!confirm('Permanently delete this question? This cannot be undone.')) return;
            try {
                await api(`questions/${id}/permanent_delete/`, 'DELETE');
                showNotification('Question permanently deleted', 'success');
                loadTrash();
            } catch (err) {
                console.error('Failed to permanently delete question:', err);
                showNotification('Failed to delete question', 'error');
            }
        }

        async function emptyTrash() {
            if (!confirm('Permanently delete all items in trash? This cannot be undone.')) return;
            try {
                const result = await api('questions/empty_trash/', 'POST');
                showNotification(`Deleted ${result.deleted} questions permanently`, 'success');
                loadTrash();
            } catch (err) {
                console.error('Failed to empty trash:', err);
                showNotification('Failed to empty trash', 'error');
            }
        }

        async function updateTrashCount(count = null) {
            if (count === null) {
                try {
                    const data = await api('questions/trash_count/');
                    count = data.count;
                } catch (err) {
                    count = 0;
                }
            }
            const badge = document.getElementById('nav-trash-count');
            if (badge) {
                badge.textContent = count;
                badge.classList.toggle('hidden', count === 0);
            }
        }

        // Load usage statistics for sidebar
        async function loadUsageStats() {
            try {
                const data = await api('questions/usage_stats/');
                const container = document.getElementById('usage-stats-mini');
                const rateEl = document.getElementById('stat-usage-rate');
                const barEl = document.getElementById('stat-usage-bar');

                // Update the total questions count in quick stats
                if (data.total_questions !== undefined) {
                    document.getElementById('stat-questions').textContent = data.total_questions;
                }

                if (container && data.total_questions > 0) {
                    container.classList.remove('hidden');
                    if (rateEl) rateEl.textContent = `${data.usage_rate}%`;
                    if (barEl) barEl.style.width = `${data.usage_rate}%`;
                }
            } catch (err) {
                console.log('Failed to load usage stats:', err);
            }
        }

        // Export questions
        async function exportQuestions(format) {
            const params = new URLSearchParams();
            const course = document.getElementById('filter-course')?.value;
            if (course) params.append('course', course);
            selectedTags.forEach(tag => params.append('tags', tag));

            const data = await api(`questions/?${params.toString()}&page_size=1000`);
            const questions = data.results || data || [];

            if (format === 'json') {
                const blob = new Blob([JSON.stringify(questions, null, 2)], { type: 'application/json' });
                downloadBlob(blob, 'questions.json');
            } else if (format === 'csv') {
                const headers = ['id', 'type', 'text', 'points', 'difficulty', 'answer'];
                const rows = questions.map(q => [
                    q.id,
                    q.question_type,
                    `"${(q.text || '').replace(/"/g, '""')}"`,
                    q.points,
                    q.difficulty,
                    `"${JSON.stringify(q.answer_data || {}).replace(/"/g, '""')}"`
                ]);
                const csv = [headers.join(','), ...rows.map(r => r.join(','))].join('\n');
                const blob = new Blob([csv], { type: 'text/csv' });
                downloadBlob(blob, 'questions.csv');
            }
        }

        function downloadBlob(blob, filename) {
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = filename;
            a.click();
            URL.revokeObjectURL(url);
        }

        // Import questions from file
        function openImportModal() {
            showModal('import-modal');
        }

        async function importQuestions() {
            const fileInput = document.getElementById('import-file');
            const bankId = document.getElementById('import-bank').value;
            if (!fileInput.files.length) return alert('Please select a file');
            if (!bankId) return alert('Please select a question bank');

            const file = fileInput.files[0];
            const text = await file.text();
            let questions;

            try {
                if (file.name.endsWith('.json')) {
                    questions = JSON.parse(text);
                } else if (file.name.endsWith('.csv')) {
                    // Simple CSV parsing
                    const lines = text.split('\n');
                    const headers = lines[0].split(',');
                    questions = lines.slice(1).filter(l => l.trim()).map(line => {
                        const values = line.match(/(".*?"|[^,]+)/g) || [];
                        const obj = {};
                        headers.forEach((h, i) => {
                            let val = values[i] || '';
                            if (val.startsWith('"') && val.endsWith('"')) val = val.slice(1, -1).replace(/""/g, '"');
                            obj[h.trim()] = val;
                        });
                        return obj;
                    });
                } else {
                    return alert('Unsupported file format. Use .json or .csv');
                }
            } catch (e) {
                return alert('Error parsing file: ' + e.message);
            }

            let imported = 0;
            for (const q of questions) {
                try {
                    await api('questions/', 'POST', {
                        question_bank: parseInt(bankId),
                        question_type: q.question_type || q.type || 'shortAnswer',
                        text: q.text || '',
                        points: parseFloat(q.points) || 2,
                        difficulty: q.difficulty || 'medium',
                        answer_data: typeof q.answer_data === 'string' ? JSON.parse(q.answer_data) : (q.answer_data || {}),
                    });
                    imported++;
                } catch (e) {
                    console.error('Failed to import question:', e);
                }
            }

            hideModal('import-modal');
            loadQuestions();
            alert(`Imported ${imported} questions`);
        }

        // Block variant preview functions
        function previewBlockVariant(event, index) {
            const row = event.target.closest('.question-row');
            if (!row) return;
            const variants = row.dataset.blockVariants;
            if (!variants) return;
            try {
                const data = JSON.parse(variants);
                if (data[index]) {
                    const textEl = row.querySelector('.question-text');
                    const pointsEl = row.querySelector('.question-points');
                    if (textEl) textEl.textContent = data[index].text;
                    if (pointsEl) pointsEl.textContent = parseInt(data[index].points);
                }
            } catch (e) { console.error('Error parsing block variants:', e); }
        }
        function resetBlockPreview(event) {
            const row = event.target.closest('.question-row');
            if (!row) return;
            const textEl = row.querySelector('.question-text');
            const pointsEl = row.querySelector('.question-points');
            if (textEl) textEl.textContent = row.dataset.originalText || '';
            if (pointsEl) pointsEl.textContent = row.dataset.originalPoints || '';
        }

        // Build Exam panel variant preview functions
        function previewExamBlockVariant(event, index) {
            const row = event.target.closest('.exam-question-row');
            if (!row) return;
            const variants = row.dataset.blockVariants;
            if (!variants) return;
            try {
                const data = JSON.parse(variants);
                if (data[index]) {
                    const textEl = row.querySelector('.exam-question-text');
                    const pointsEl = row.querySelector('.exam-question-points');
                    if (textEl) textEl.textContent = data[index].text;
                    if (pointsEl) pointsEl.textContent = parseInt(data[index].points) + ' pts';
                }
            } catch (e) { console.error('Error parsing block variants:', e); }
        }
        function resetExamBlockPreview(event) {
            const row = event.target.closest('.exam-question-row');
            if (!row) return;
            const textEl = row.querySelector('.exam-question-text');
            const pointsEl = row.querySelector('.exam-question-points');
            if (textEl) textEl.textContent = row.dataset.originalText || '';
            if (pointsEl) pointsEl.textContent = (row.dataset.originalPoints || '') + ' pts';
        }

        // ========== Sharing Functions ==========
        let currentShareType = null;  // 'course', 'bank', or 'template'
        let currentShareId = null;    // The ID/code of the item being shared

        async function openShareModal(type, id) {
            currentShareType = type;
            currentShareId = id;

            // Update modal title
            const titles = { course: 'Share Course', bank: 'Share Question Bank', template: 'Share Exam Template' };
            document.getElementById('share-modal-title').textContent = titles[type] || 'Share';

            // Clear search input
            document.getElementById('share-user-search').value = '';
            document.getElementById('share-user-results').classList.add('hidden');
            document.getElementById('share-user-results').innerHTML = '';

            // Load current shares
            await loadCurrentShares();

            showModal('share-modal');
            lucide.createIcons();
        }

        async function loadCurrentShares() {
            const container = document.getElementById('current-shares');
            container.innerHTML = '<p class="text-sm text-gray-400">Loading...</p>';

            try {
                let endpoint;
                switch (currentShareType) {
                    case 'course':
                        endpoint = `courses/${currentShareId}/shares/`;
                        break;
                    case 'bank':
                        endpoint = `banks/${currentShareId}/shares/`;
                        break;
                    case 'template':
                        endpoint = `exams/templates/${currentShareId}/shares/`;
                        break;
                }

                const shares = await api(endpoint);
                const sharesArray = shares.results || shares || [];

                if (sharesArray.length === 0) {
                    container.innerHTML = '<p class="text-sm text-gray-400 dark:text-slate-500">Not shared with anyone</p>';
                    return;
                }

                container.innerHTML = sharesArray.map(share => `
                    <div class="flex items-center justify-between p-2 bg-gray-50 dark:bg-slate-700/50 rounded-lg">
                        <div class="flex items-center gap-2">
                            <div class="w-8 h-8 rounded-full bg-gradient-to-br from-sky-400 to-cyan-500 flex items-center justify-center text-white font-bold text-sm">
                                ${(share.shared_with_username || 'U')[0].toUpperCase()}
                            </div>
                            <div>
                                <div class="text-sm font-medium text-gray-700 dark:text-slate-300">${escapeHtml(share.shared_with_username)}</div>
                                <div class="text-xs text-gray-400 dark:text-slate-500">${share.permission === 'edit' ? 'Can Edit' : 'View Only'}</div>
                            </div>
                        </div>
                        <button onclick="removeShare('${share.shared_with_username}')" class="p-1.5 rounded hover:bg-red-100 dark:hover:bg-red-900/30 text-gray-400 hover:text-red-500" title="Remove access">
                            <i data-lucide="x" class="w-4 h-4"></i>
                        </button>
                    </div>
                `).join('');
                lucide.createIcons();
            } catch (err) {
                console.error('Error loading shares:', err);
                container.innerHTML = '<p class="text-sm text-red-500">Error loading shares</p>';
            }
        }

        const searchUsersDebounced = debounce(searchUsers, 300);

        async function searchUsers() {
            const query = document.getElementById('share-user-search').value.trim();
            const resultsContainer = document.getElementById('share-user-results');

            if (query.length < 2) {
                resultsContainer.classList.add('hidden');
                return;
            }

            try {
                const users = await api(`users/?search=${encodeURIComponent(query)}`);
                const usersArray = users.results || users || [];

                if (usersArray.length === 0) {
                    resultsContainer.innerHTML = '<div class="p-3 text-sm text-gray-400">No users found</div>';
                } else {
                    resultsContainer.innerHTML = usersArray.map(user => `
                        <button onclick="selectUserToShare('${escapeHtml(user.username)}')"
                            class="w-full text-left px-3 py-2 hover:bg-gray-100 dark:hover:bg-slate-700 flex items-center gap-2">
                            <div class="w-8 h-8 rounded-full bg-gradient-to-br from-emerald-400 to-cyan-500 flex items-center justify-center text-white font-bold text-sm">
                                ${(user.username || 'U')[0].toUpperCase()}
                            </div>
                            <div>
                                <div class="text-sm font-medium text-gray-700 dark:text-slate-300">${escapeHtml(user.username)}</div>
                                <div class="text-xs text-gray-400 dark:text-slate-500">${escapeHtml(user.email || '')}</div>
                            </div>
                        </button>
                    `).join('');
                }
                resultsContainer.classList.remove('hidden');
            } catch (err) {
                console.error('Error searching users:', err);
            }
        }

        async function selectUserToShare(username) {
            const permission = document.getElementById('share-permission').value;
            document.getElementById('share-user-results').classList.add('hidden');
            document.getElementById('share-user-search').value = '';

            try {
                let endpoint;
                switch (currentShareType) {
                    case 'course':
                        endpoint = `courses/${currentShareId}/share/`;
                        break;
                    case 'bank':
                        endpoint = `banks/${currentShareId}/share/`;
                        break;
                    case 'template':
                        endpoint = `exams/templates/${currentShareId}/share/`;
                        break;
                }

                await api(endpoint, 'POST', { username, permission });
                await loadCurrentShares();
            } catch (err) {
                console.error('Error sharing:', err);
                alert('Error sharing. Please try again.');
            }
        }

        async function removeShare(username) {
            if (!confirm(`Remove ${username}'s access?`)) return;

            try {
                let endpoint;
                switch (currentShareType) {
                    case 'course':
                        endpoint = `courses/${currentShareId}/unshare/`;
                        break;
                    case 'bank':
                        endpoint = `banks/${currentShareId}/unshare/`;
                        break;
                    case 'template':
                        endpoint = `exams/templates/${currentShareId}/unshare/`;
                        break;
                }

                await api(endpoint, 'DELETE', { username });
                await loadCurrentShares();
            } catch (err) {
                console.error('Error removing share:', err);
                alert('Error removing share. Please try again.');
            }
        }

        async function copyBank(bankId) {
            const newName = prompt('Name for the copy:');
            if (!newName) return;

            try {
                await api(`banks/${bankId}/copy/`, 'POST', { name: newName });
                await loadBanks();
                alert('Bank copied successfully!');
            } catch (err) {
                console.error('Error copying bank:', err);
                alert('Error copying bank. Please try again.');
            }
        }

        async function copyTemplate(templateId) {
            const newName = prompt('Name for the copy:');
            if (!newName) return;

            try {
                await api(`exams/templates/${templateId}/copy/`, 'POST', { name: newName });
                await loadExamTemplates(currentTemplateFilter);
                showToast('Template copied', 'success');
            } catch (err) {
                console.error('Error copying template:', err);
                showToast('Error copying template', 'error');
            }
        }

        // ===============================
        // LIVE QUIZZES SECTION
        // ===============================

        let currentQuizSessionId = null;
        let quizSessions = [];

        async function loadQuizSessions(status = '') {
            try {
                let url = 'quizzes/sessions/';
                if (status) url += `?status=${status}`;
                const data = await api(url);
                quizSessions = data.results || data || [];
                renderQuizSessions();
            } catch (err) {
                console.error('Error loading quiz sessions:', err);
            }
        }

        function renderQuizSessions() {
            const container = document.getElementById('quiz-sessions-list');
            if (!quizSessions.length) {
                container.innerHTML = `
                    <div class="p-12 text-center text-gray-400 dark:text-slate-500">
                        <i data-lucide="play-circle" class="w-12 h-12 mx-auto mb-3 opacity-50"></i>
                        <p>No quiz sessions found</p>
                    </div>`;
                lucide.createIcons();
                return;
            }

            container.innerHTML = quizSessions.map(q => `
                <div class="p-4 hover:bg-gray-50 dark:hover:bg-slate-700/50 transition-colors">
                    <div class="flex items-start justify-between">
                        <div class="flex-1">
                            <div class="flex items-center gap-2 mb-1">
                                <span class="font-medium text-gray-900 dark:text-white">${escapeHtml(q.name)}</span>
                                <span class="badge ${getStatusBadgeClass(q.status)}">${q.status}</span>
                            </div>
                            <p class="text-sm text-gray-500 dark:text-slate-400 mb-2">
                                ${q.course_code || ''} ${q.template_name ? `• Template: ${q.template_name}` : ''}
                            </p>
                            <div class="flex items-center gap-4 text-sm">
                                <span class="flex items-center gap-1 text-gray-500 dark:text-slate-400">
                                    <i data-lucide="clock" class="w-4 h-4"></i>
                                    ${q.time_limit_minutes} min
                                </span>
                                <span class="flex items-center gap-1 text-gray-500 dark:text-slate-400">
                                    <i data-lucide="users" class="w-4 h-4"></i>
                                    ${q.submission_count || 0} submissions
                                </span>
                                ${q.status === 'active' ? `
                                    <span class="flex items-center gap-1 text-emerald-600 dark:text-emerald-400 font-mono font-bold">
                                        <i data-lucide="key" class="w-4 h-4"></i>
                                        ${q.access_code}
                                    </span>
                                ` : ''}
                            </div>
                        </div>
                        <div class="flex items-center gap-2">
                            ${q.status === 'draft' ? `
                                <button onclick="activateQuiz('${q.id}')" class="px-3 py-1.5 text-sm bg-emerald-100 dark:bg-emerald-900/50 text-emerald-700 dark:text-emerald-300 rounded-lg hover:bg-emerald-200 flex items-center gap-1">
                                    <i data-lucide="play" class="w-4 h-4"></i>Activate
                                </button>
                            ` : ''}
                            ${q.status === 'active' ? `
                                <button onclick="closeQuiz('${q.id}')" class="px-3 py-1.5 text-sm bg-orange-100 dark:bg-orange-900/50 text-orange-700 dark:text-orange-300 rounded-lg hover:bg-orange-200 flex items-center gap-1">
                                    <i data-lucide="square" class="w-4 h-4"></i>Close
                                </button>
                            ` : ''}
                            <button onclick="viewRoster('${q.id}', '${escapeHtml(q.name)}')" class="px-3 py-1.5 text-sm bg-violet-100 dark:bg-violet-900/50 text-violet-700 dark:text-violet-300 rounded-lg hover:bg-violet-200 flex items-center gap-1">
                                <i data-lucide="users" class="w-4 h-4"></i>Roster
                            </button>
                            <button onclick="previewQuiz('${q.id}')" class="px-3 py-1.5 text-sm bg-indigo-100 dark:bg-indigo-900/50 text-indigo-700 dark:text-indigo-300 rounded-lg hover:bg-indigo-200 flex items-center gap-1" title="Preview quiz as student">
                                <i data-lucide="eye" class="w-4 h-4"></i>Preview
                            </button>
                            <button onclick="viewQuizQuestions('${q.id}', '${escapeHtml(q.name)}')" class="px-3 py-1.5 text-sm bg-cyan-100 dark:bg-cyan-900/50 text-cyan-700 dark:text-cyan-300 rounded-lg hover:bg-cyan-200 flex items-center gap-1" title="View/edit quiz questions">
                                <i data-lucide="help-circle" class="w-4 h-4"></i>Questions
                            </button>
                            <button onclick="viewSubmissions('${q.id}', '${escapeHtml(q.name)}')" class="px-3 py-1.5 text-sm bg-gray-100 dark:bg-slate-700 text-gray-700 dark:text-slate-300 rounded-lg hover:bg-gray-200 flex items-center gap-1">
                                <i data-lucide="list" class="w-4 h-4"></i>Submissions
                            </button>
                            <button onclick="editQuizSession('${q.id}')" class="p-2 text-gray-400 hover:text-sky-600 hover:bg-sky-50 dark:hover:bg-sky-900/30 rounded-lg">
                                <i data-lucide="edit-2" class="w-4 h-4"></i>
                            </button>
                            <button onclick="deleteQuizSession('${q.id}')" class="p-2 text-gray-400 hover:text-red-600 hover:bg-red-50 dark:hover:bg-red-900/30 rounded-lg">
                                <i data-lucide="trash-2" class="w-4 h-4"></i>
                            </button>
                        </div>
                    </div>
                </div>
            `).join('');
            lucide.createIcons();
        }

        function getStatusBadgeClass(status) {
            switch (status) {
                case 'active': return 'bg-emerald-100 dark:bg-emerald-900/50 text-emerald-700 dark:text-emerald-300';
                case 'closed': return 'bg-gray-100 dark:bg-slate-700 text-gray-700 dark:text-slate-300';
                case 'draft': return 'bg-yellow-100 dark:bg-yellow-900/50 text-yellow-700 dark:text-yellow-300';
                default: return 'bg-gray-100 dark:bg-slate-700 text-gray-600 dark:text-slate-400';
            }
        }

        async function openNewQuizModal() {
            document.getElementById('quiz-edit-id').value = '';
            document.getElementById('quiz-name').value = '';
            document.getElementById('quiz-description').value = '';
            document.getElementById('quiz-instructions').value = '';
            document.getElementById('quiz-time-limit').value = '30';
            document.getElementById('quiz-max-attempts').value = '1';
            document.getElementById('quiz-shuffle-questions').checked = true;
            document.getElementById('quiz-shuffle-answers').checked = true;
            document.getElementById('quiz-require-student-id').checked = false;
            document.getElementById('quiz-show-score').checked = true;
            document.getElementById('quiz-show-answers').checked = false;
            document.getElementById('quiz-ai-grading').checked = true;
            document.getElementById('quiz-ai-provider').value = 'claude';
            document.getElementById('quiz-modal-title').textContent = 'Create Quiz Session';

            // Load templates for dropdown
            await loadQuizTemplateOptions();

            showModal('quiz-modal');
        }

        async function loadQuizTemplateOptions() {
            try {
                const data = await api('exams/templates/');
                const templates = data.results || data || [];
                const select = document.getElementById('quiz-template');
                select.innerHTML = '<option value="">Select a template to use its questions...</option>' +
                    templates.map(t => `<option value="${t.id}">${escapeHtml(t.name)} (${t.course_code || 'No course'})</option>`).join('');
            } catch (err) {
                console.error('Error loading templates:', err);
            }
        }

        async function saveQuizSession() {
            const id = document.getElementById('quiz-edit-id').value;
            const name = document.getElementById('quiz-name').value.trim();
            if (!name) return alert('Please enter a quiz name');

            const data = {
                name,
                description: document.getElementById('quiz-description').value.trim(),
                instructions: document.getElementById('quiz-instructions').value.trim(),
                time_limit_minutes: parseInt(document.getElementById('quiz-time-limit').value) || 30,
                max_attempts: parseInt(document.getElementById('quiz-max-attempts').value) || 1,
                shuffle_questions: document.getElementById('quiz-shuffle-questions').checked,
                shuffle_answers: document.getElementById('quiz-shuffle-answers').checked,
                require_student_id: document.getElementById('quiz-require-student-id').checked,
                show_score_immediately: document.getElementById('quiz-show-score').checked,
                show_correct_answers: document.getElementById('quiz-show-answers').checked,
                ai_grading_enabled: document.getElementById('quiz-ai-grading').checked,
                ai_grading_provider: document.getElementById('quiz-ai-provider').value,
            };

            const templateId = document.getElementById('quiz-template').value;
            if (templateId) {
                data.template = parseInt(templateId);
            }

            try {
                if (id) {
                    await api(`quizzes/sessions/${id}/`, 'PATCH', data);
                } else {
                    await api('quizzes/sessions/', 'POST', data);
                }
                hideModal('quiz-modal');
                await loadQuizSessions();
            } catch (err) {
                console.error('Error saving quiz:', err);
                alert('Error saving quiz. Please try again.');
            }
        }

        async function editQuizSession(id) {
            try {
                const quiz = await api(`quizzes/sessions/${id}/`);
                document.getElementById('quiz-edit-id').value = id;
                document.getElementById('quiz-name').value = quiz.name || '';
                document.getElementById('quiz-description').value = quiz.description || '';
                document.getElementById('quiz-instructions').value = quiz.instructions || '';
                document.getElementById('quiz-time-limit').value = quiz.time_limit_minutes || 30;
                document.getElementById('quiz-max-attempts').value = quiz.max_attempts || 1;
                document.getElementById('quiz-shuffle-questions').checked = quiz.shuffle_questions !== false;
                document.getElementById('quiz-shuffle-answers').checked = quiz.shuffle_answers !== false;
                document.getElementById('quiz-require-student-id').checked = quiz.require_student_id || false;
                document.getElementById('quiz-show-score').checked = quiz.show_score_immediately !== false;
                document.getElementById('quiz-show-answers').checked = quiz.show_correct_answers || false;
                document.getElementById('quiz-ai-grading').checked = quiz.ai_grading_enabled !== false;
                document.getElementById('quiz-ai-provider').value = quiz.ai_grading_provider || 'claude';
                document.getElementById('quiz-modal-title').textContent = 'Edit Quiz Session';

                await loadQuizTemplateOptions();
                if (quiz.template) {
                    document.getElementById('quiz-template').value = quiz.template;
                }

                showModal('quiz-modal');
            } catch (err) {
                console.error('Error loading quiz:', err);
                alert('Error loading quiz. Please try again.');
            }
        }

        async function deleteQuizSession(id) {
            if (!confirm('Delete this quiz session? This will also delete all submissions.')) return;
            try {
                await api(`quizzes/sessions/${id}/`, 'DELETE');
                await loadQuizSessions();
            } catch (err) {
                console.error('Error deleting quiz:', err);
                alert('Error deleting quiz. Please try again.');
            }
        }

        async function activateQuiz(id) {
            try {
                await api(`quizzes/sessions/${id}/activate/`, 'POST');
                await loadQuizSessions();
            } catch (err) {
                console.error('Error activating quiz:', err);
                alert('Error activating quiz. Please try again.');
            }
        }

        async function closeQuiz(id) {
            if (!confirm('Close this quiz? Students will no longer be able to start new attempts.')) return;
            try {
                await api(`quizzes/sessions/${id}/close/`, 'POST');
                await loadQuizSessions();
            } catch (err) {
                console.error('Error closing quiz:', err);
                alert('Error closing quiz. Please try again.');
            }
        }

        function copyAccessCode(code) {
            const url = `${window.location.origin}/quiz/${code}/`;
            navigator.clipboard.writeText(url);
            alert(`Quiz link copied to clipboard:\n${url}`);
        }

        function previewQuiz(quizId) {
            // Open quiz preview in a new tab
            window.open(`/quiz/preview/${quizId}/`, '_blank');
        }

        // ===============================
        // QUIZ QUESTIONS MANAGEMENT
        // ===============================
        let currentQuizQuestionsId = null;

        async function viewQuizQuestions(quizId, quizName) {
            currentQuizQuestionsId = quizId;
            document.getElementById('quiz-questions-name').textContent = quizName;

            try {
                const data = await api(`quizzes/sessions/${quizId}/questions/`);
                const questions = data.questions || [];
                renderQuizQuestions(questions, data.source);
                showModal('quiz-questions-modal');
                lucide.createIcons();
            } catch (err) {
                console.error('Error loading quiz questions:', err);
                alert('Error loading questions. Please try again.');
            }
        }

        function renderQuizQuestions(questions, source) {
            const container = document.getElementById('quiz-questions-list');

            if (!questions.length) {
                container.innerHTML = `
                    <div class="text-center text-gray-400 dark:text-slate-500 py-8">
                        <i data-lucide="help-circle" class="w-12 h-12 mx-auto mb-3 opacity-50"></i>
                        <p>No questions found for this quiz</p>
                    </div>`;
                return;
            }

            container.innerHTML = `
                <div class="mb-4 text-sm text-gray-500 dark:text-slate-400">
                    ${questions.length} questions • Source: ${source}
                </div>
                ${questions.map((q, i) => `
                    <div class="border dark:border-slate-700 rounded-lg p-4 hover:bg-gray-50 dark:hover:bg-slate-700/50">
                        <div class="flex items-start justify-between mb-2">
                            <div class="flex items-center gap-2">
                                <span class="text-sm font-medium text-gray-500 dark:text-slate-400">Q${i + 1}</span>
                                <span class="badge ${getQuestionTypeBadge(q.question_type)}">${q.question_type}</span>
                                <span class="text-xs text-gray-400">${q.points} pts</span>
                            </div>
                            <button onclick="editQuestionInQuiz(${q.id})" class="text-sky-500 hover:text-sky-600 text-sm flex items-center gap-1">
                                <i data-lucide="edit-2" class="w-3 h-3"></i>Edit
                            </button>
                        </div>
                        <div class="text-gray-900 dark:text-white mb-2">${escapeHtml(q.text)}</div>
                        ${q.question_type === 'multipleChoice' && q.answer_data?.choices ? `
                            <div class="text-sm text-gray-600 dark:text-slate-400 ml-4">
                                ${q.answer_data.choices.map((c, ci) => `
                                    <div class="${c === q.answer_data.correct ? 'text-emerald-600 dark:text-emerald-400 font-medium' : ''}">
                                        ${String.fromCharCode(65 + ci)}. ${escapeHtml(c)} ${c === q.answer_data.correct ? '✓' : ''}
                                    </div>
                                `).join('')}
                            </div>
                        ` : ''}
                        ${q.question_type === 'trueFalse' ? `
                            <div class="text-sm text-emerald-600 dark:text-emerald-400 ml-4">
                                Answer: ${q.answer_data?.correct ? 'True' : 'False'}
                            </div>
                        ` : ''}
                    </div>
                `).join('')}
            `;
        }

        function editQuestionInQuiz(questionId) {
            // Navigate to the questions tab and select this question for editing
            hideModal('quiz-questions-modal');
            showSection('questions');
            // Load the question for editing
            setTimeout(() => editQuestion(questionId), 300);
        }

        // ===============================
        // ROSTER / INVITATIONS MANAGEMENT
        // ===============================
        let currentRosterQuizId = null;

        async function viewRoster(quizId, quizName) {
            currentRosterQuizId = quizId;
            document.getElementById('roster-quiz-name').textContent = `Roster: ${quizName}`;
            document.getElementById('quiz-roster-section').classList.remove('hidden');
            await loadInvitations(quizId);
        }

        function hideRoster() {
            document.getElementById('quiz-roster-section').classList.add('hidden');
            currentRosterQuizId = null;
        }

        async function loadInvitations(quizId) {
            try {
                const data = await api(`quizzes/invitations/?quiz_session=${quizId}`);
                const invitations = data.results || data || [];
                renderInvitations(invitations);
            } catch (err) {
                console.error('Error loading invitations:', err);
            }
        }

        function renderInvitations(invitations) {
            const container = document.getElementById('quiz-invitations-list');
            if (!invitations.length) {
                container.innerHTML = `
                    <div class="p-8 text-center text-gray-400 dark:text-slate-500">
                        <i data-lucide="users" class="w-10 h-10 mx-auto mb-2 opacity-50"></i>
                        <p>No students added yet. Import a roster to get started.</p>
                    </div>`;
                lucide.createIcons();
                return;
            }

            container.innerHTML = invitations.map(inv => `
                <div class="p-3 hover:bg-gray-50 dark:hover:bg-slate-700/50 transition-colors flex items-center justify-between">
                    <div class="flex-1 min-w-0">
                        <div class="font-medium text-gray-900 dark:text-white truncate">${escapeHtml(inv.student_name)}</div>
                        <div class="text-sm text-gray-500 dark:text-slate-400 truncate">${escapeHtml(inv.student_email)}</div>
                    </div>
                    <div class="flex items-center gap-2 ml-4">
                        ${inv.is_used ? `
                            <span class="px-2 py-1 bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400 text-xs rounded-full">Completed</span>
                        ` : inv.email_sent_at ? `
                            <span class="px-2 py-1 bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400 text-xs rounded-full">Sent</span>
                        ` : `
                            <span class="px-2 py-1 bg-gray-100 text-gray-600 dark:bg-slate-700 dark:text-slate-400 text-xs rounded-full">Pending</span>
                        `}
                        <button onclick="copyInviteLink('${inv.code}')" class="p-1 text-gray-400 hover:text-gray-600 dark:hover:text-slate-300" title="Copy invite link">
                            <i data-lucide="link" class="w-4 h-4"></i>
                        </button>
                    </div>
                </div>
            `).join('');
            lucide.createIcons();
        }

        function copyInviteLink(code) {
            const url = `${window.location.origin}/quiz/${code}/`;
            navigator.clipboard.writeText(url);
            alert(`Personal quiz link copied:\n${url}`);
        }

        function showRosterImport() {
            document.getElementById('roster-import-area').classList.toggle('hidden');
        }

        async function importRoster() {
            if (!currentRosterQuizId) return;

            const fileInput = document.getElementById('roster-file-input');
            const textInput = document.getElementById('roster-text-input');

            let formData = new FormData();

            if (fileInput.files.length > 0) {
                formData.append('file', fileInput.files[0]);
            } else if (textInput.value.trim()) {
                // Parse text input (email per line or CSV format)
                const lines = textInput.value.trim().split('\n');
                const students = lines.map(line => {
                    const parts = line.split(',').map(p => p.trim());
                    if (parts.length >= 2) {
                        return { email: parts[0], name: parts[1], student_id: parts[2] || '' };
                    } else {
                        return { email: parts[0], name: parts[0].split('@')[0] };
                    }
                }).filter(s => s.email && s.email.includes('@'));

                formData.append('students', JSON.stringify(students));
            } else {
                alert('Please upload a CSV file or enter student emails');
                return;
            }

            try {
                const response = await fetch(`/api/quizzes/sessions/${currentRosterQuizId}/roster/import/`, {
                    method: 'POST',
                    headers: {
                        'X-CSRFToken': getCSRFToken()
                    },
                    body: formData
                });
                const data = await response.json();

                if (data.success) {
                    alert(`Imported ${data.created} students (${data.skipped} already existed)`);
                    document.getElementById('roster-import-area').classList.add('hidden');
                    fileInput.value = '';
                    textInput.value = '';
                    await loadInvitations(currentRosterQuizId);
                } else {
                    alert('Import error: ' + (data.error || 'Unknown error'));
                }
            } catch (err) {
                console.error('Error importing roster:', err);
                alert('Error importing roster. Please try again.');
            }
        }

        async function sendAllInvitations() {
            if (!currentRosterQuizId) return;
            if (!confirm("Send quiz invitation emails to all students who haven't received one yet?")) return;

            try {
                const data = await api(`quizzes/sessions/${currentRosterQuizId}/invitations/send/`, 'POST', {});
                alert(`Sent ${data.sent} emails${data.failed > 0 ? ` (${data.failed} failed)` : ''}`);
                await loadInvitations(currentRosterQuizId);
            } catch (err) {
                console.error('Error sending invitations:', err);
                alert('Error sending invitations: ' + (err.message || 'Unknown error'));
            }
        }

        // Submissions management
        async function viewSubmissions(quizId, quizName) {
            currentQuizSessionId = quizId;
            document.getElementById('submissions-quiz-name').textContent = `Submissions: ${quizName}`;
            document.getElementById('quiz-submissions-section').classList.remove('hidden');

            try {
                const data = await api(`quizzes/submissions/?quiz_session=${quizId}`);
                const submissions = data.results || data || [];
                renderSubmissions(submissions);
            } catch (err) {
                console.error('Error loading submissions:', err);
            }
        }

        function hideSubmissions() {
            document.getElementById('quiz-submissions-section').classList.add('hidden');
            currentQuizSessionId = null;
        }

        function renderSubmissions(submissions) {
            const container = document.getElementById('quiz-submissions-list');
            if (!submissions.length) {
                container.innerHTML = `
                    <div class="p-8 text-center text-gray-400 dark:text-slate-500">
                        <i data-lucide="inbox" class="w-10 h-10 mx-auto mb-2 opacity-50"></i>
                        <p>No submissions yet</p>
                    </div>`;
                lucide.createIcons();
                return;
            }

            container.innerHTML = submissions.map(s => `
                <div class="p-4 hover:bg-gray-50 dark:hover:bg-slate-700/50 transition-colors">
                    <div class="flex items-center justify-between">
                        <div class="flex-1">
                            <div class="flex items-center gap-2 mb-1">
                                <span class="font-medium text-gray-900 dark:text-white">${escapeHtml(s.student_name)}</span>
                                ${s.student_id ? `<span class="text-sm text-gray-500 dark:text-slate-400">(${s.student_id})</span>` : ''}
                                <span class="badge ${getSubmissionStatusClass(s.status)}">${s.status}</span>
                                ${s.is_late ? '<span class="badge bg-red-100 dark:bg-red-900/50 text-red-700 dark:text-red-300">Late</span>' : ''}
                            </div>
                            <div class="flex items-center gap-4 text-sm text-gray-500 dark:text-slate-400">
                                <span>Submitted: ${s.submitted_at ? new Date(s.submitted_at).toLocaleString() : 'In progress'}</span>
                                ${s.percentage_score != null ? `
                                    <span class="font-medium ${s.percentage_score >= 70 ? 'text-emerald-600' : s.percentage_score >= 50 ? 'text-yellow-600' : 'text-red-600'}">
                                        ${Number(s.percentage_score).toFixed(1)}% (${s.total_points_earned || 0}/${s.total_points_possible || 0} pts)
                                    </span>
                                ` : ''}
                            </div>
                        </div>
                        <div class="flex items-center gap-2">
                            ${s.status === 'submitted' ? `
                                <button onclick="gradeSubmission('${s.id}')" class="px-3 py-1.5 text-sm bg-purple-100 dark:bg-purple-900/50 text-purple-700 dark:text-purple-300 rounded-lg hover:bg-purple-200 flex items-center gap-1">
                                    <i data-lucide="sparkles" class="w-4 h-4"></i>AI Grade
                                </button>
                            ` : ''}
                            <button onclick="reviewSubmission('${s.id}')" class="px-3 py-1.5 text-sm bg-sky-100 dark:bg-sky-900/50 text-sky-700 dark:text-sky-300 rounded-lg hover:bg-sky-200 flex items-center gap-1">
                                <i data-lucide="eye" class="w-4 h-4"></i>Review
                            </button>
                        </div>
                    </div>
                </div>
            `).join('');
            lucide.createIcons();
        }

        function getSubmissionStatusClass(status) {
            switch (status) {
                case 'submitted': return 'bg-sky-100 dark:bg-sky-900/50 text-sky-700 dark:text-sky-300';
                case 'graded': return 'bg-emerald-100 dark:bg-emerald-900/50 text-emerald-700 dark:text-emerald-300';
                case 'reviewed': return 'bg-purple-100 dark:bg-purple-900/50 text-purple-700 dark:text-purple-300';
                case 'in_progress': return 'bg-yellow-100 dark:bg-yellow-900/50 text-yellow-700 dark:text-yellow-300';
                default: return 'bg-gray-100 dark:bg-slate-700 text-gray-600 dark:text-slate-400';
            }
        }

        async function gradeSubmission(submissionId) {
            try {
                const result = await api(`quizzes/grade/batch/`, 'POST', { submission_id: submissionId });
                alert(`Graded ${result.graded_count} responses.`);
                if (currentQuizSessionId) {
                    viewSubmissions(currentQuizSessionId, document.getElementById('submissions-quiz-name').textContent.replace('Submissions: ', ''));
                }
            } catch (err) {
                console.error('Error grading submission:', err);
                alert('Error grading submission. Please try again.');
            }
        }

        async function gradeAllPending() {
            if (!currentQuizSessionId) return;
            try {
                const result = await api(`quizzes/grade/batch/`, 'POST', { quiz_session_id: currentQuizSessionId });
                let msg = `Graded ${result.graded_count} responses across ${result.submission_count || 'all'} submissions.`;
                if (result.errors && result.errors.length > 0) {
                    msg += `\n\nErrors (${result.errors.length}):\n` + result.errors.slice(0, 5).join('\n');
                    if (result.errors.length > 5) msg += `\n... and ${result.errors.length - 5} more`;
                }
                alert(msg);
                viewSubmissions(currentQuizSessionId, document.getElementById('submissions-quiz-name').textContent.replace('Submissions: ', ''));
            } catch (err) {
                console.error('Error grading:', err);
                alert('Error grading submissions. Please try again.');
            }
        }

        async function reviewSubmission(submissionId) {
            try {
                const submission = await api(`quizzes/submissions/${submissionId}/`);
                document.getElementById('submission-student-name').textContent =
                    `${submission.student_name}${submission.student_id ? ` (${submission.student_id})` : ''} - ${new Date(submission.submitted_at || submission.started_at).toLocaleString()}`;

                const totalPossible = submission.total_points_possible || 0;
                const totalEarned = submission.total_points_earned || 0;
                const pct = totalPossible > 0 ? ((totalEarned / totalPossible) * 100).toFixed(1) : 0;
                document.getElementById('submission-total-score').textContent = `${totalEarned}/${totalPossible} pts (${pct}%)`;

                const responses = submission.responses || [];
                document.getElementById('submission-responses').innerHTML = responses.map((r, idx) => `
                    <div class="border border-gray-200 dark:border-slate-700 rounded-xl p-4">
                        <div class="flex items-start justify-between mb-3">
                            <div>
                                <span class="font-medium text-gray-900 dark:text-white">Question ${r.question_number || idx + 1}</span>
                                <span class="ml-2 badge ${getQuestionTypeBadge(r.question_type)}">${formatQuestionType(r.question_type)}</span>
                            </div>
                            <div class="flex items-center gap-2">
                                <span class="${r.is_correct ? 'text-emerald-600' : r.final_score !== null ? 'text-sky-600' : 'text-gray-400'} font-medium">
                                    ${r.final_score !== null ? `${r.final_score}/${r.points_possible} pts` : 'Not graded'}
                                </span>
                            </div>
                        </div>
                        <div class="text-sm text-gray-700 dark:text-slate-300 mb-3">${escapeHtml(r.question_text || '')}</div>
                        <div class="bg-gray-50 dark:bg-slate-800 rounded-lg p-3 mb-3">
                            <div class="text-xs text-gray-500 dark:text-slate-400 mb-1">Student's Answer:</div>
                            <div class="text-gray-900 dark:text-white">${escapeHtml(r.formatted_answer || '')}</div>
                        </div>
                        ${r.ai_feedback || r.override_feedback ? `
                            <div class="bg-sky-50 dark:bg-sky-900/30 rounded-lg p-3 text-sm">
                                <div class="text-xs text-sky-600 dark:text-sky-400 mb-1">Feedback:</div>
                                <div class="text-gray-700 dark:text-slate-300">${escapeHtml(r.override_feedback || r.ai_feedback)}</div>
                            </div>
                        ` : ''}
                        <div class="mt-3 flex items-center gap-2">
                            <input type="number" id="override-score-${r.id}" value="${r.final_score || ''}" min="0" max="${r.points_possible}"
                                class="input-modern w-20 px-2 py-1 rounded text-sm" placeholder="Score">
                            <span class="text-sm text-gray-500">/ ${r.points_possible}</span>
                            <input type="text" id="override-feedback-${r.id}" value="${escapeHtml(r.override_feedback || '')}"
                                class="input-modern flex-1 px-2 py-1 rounded text-sm" placeholder="Override feedback (optional)">
                            <button onclick="overrideGrade('${r.id}')" class="px-3 py-1 text-sm bg-orange-100 dark:bg-orange-900/50 text-orange-700 dark:text-orange-300 rounded-lg hover:bg-orange-200">
                                Override
                            </button>
                        </div>
                    </div>
                `).join('');

                showModal('submission-modal');
                lucide.createIcons();
            } catch (err) {
                console.error('Error loading submission:', err);
                alert('Error loading submission. Please try again.');
            }
        }

        function getQuestionTypeBadge(type) {
            switch (type) {
                case 'multipleChoice': return 'bg-blue-100 dark:bg-blue-900/50 text-blue-700 dark:text-blue-300';
                case 'trueFalse': return 'bg-purple-100 dark:bg-purple-900/50 text-purple-700 dark:text-purple-300';
                case 'shortAnswer': return 'bg-amber-100 dark:bg-amber-900/50 text-amber-700 dark:text-amber-300';
                case 'longAnswer': return 'bg-emerald-100 dark:bg-emerald-900/50 text-emerald-700 dark:text-emerald-300';
                default: return 'bg-gray-100 dark:bg-slate-700 text-gray-700 dark:text-slate-300';
            }
        }

        function formatQuestionType(type) {
            switch (type) {
                case 'multipleChoice': return 'MC';
                case 'trueFalse': return 'T/F';
                case 'shortAnswer': return 'Short';
                case 'longAnswer': return 'Long';
                default: return type || 'Unknown';
            }
        }

        function formatResponseData(data, type) {
            if (!data) return '<em class="text-gray-400">No answer</em>';
            if (type === 'multipleChoice' || type === 'trueFalse') {
                return escapeHtml(String(data.selected || data));
            }
            return escapeHtml(data.text || JSON.stringify(data));
        }

        async function overrideGrade(responseId) {
            const score = document.getElementById(`override-score-${responseId}`).value;
            const feedback = document.getElementById(`override-feedback-${responseId}`).value;

            if (score === '') return alert('Please enter a score');

            try {
                await api(`quizzes/grade/override/${responseId}/`, 'POST', {
                    score: parseFloat(score),
                    feedback: feedback || null
                });
                alert('Grade overridden successfully');
                // Refresh the submission view
                const submissionId = document.querySelector('#submission-responses [id^="override-score-"]')?.id?.split('-').pop();
                // Just close and reopen would refresh
            } catch (err) {
                console.error('Error overriding grade:', err);
                alert('Error overriding grade. Please try again.');
            }
        }

        async function exportSubmissions() {
            if (!currentQuizSessionId) return;
            try {
                const data = await api(`quizzes/submissions/?quiz_session=${currentQuizSessionId}`);
                const submissions = data.results || data || [];

                // Build CSV
                const headers = ['Student Name', 'Student ID', 'Email', 'Status', 'Submitted At', 'Points Earned', 'Points Possible', 'Percentage'];
                const rows = submissions.map(s => [
                    s.student_name,
                    s.student_id || '',
                    s.student_email || '',
                    s.status,
                    s.submitted_at || '',
                    s.total_points_earned || 0,
                    s.total_points_possible || 0,
                    s.percentage_score != null ? Number(s.percentage_score).toFixed(1) : ''
                ]);

                const csv = [headers.join(','), ...rows.map(r => r.map(c => `"${String(c).replace(/"/g, '""')}"`).join(','))].join('\n');
                const blob = new Blob([csv], { type: 'text/csv' });
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = `quiz-submissions-${currentQuizSessionId}.csv`;
                a.click();
                URL.revokeObjectURL(url);
            } catch (err) {
                console.error('Error exporting:', err);
                alert('Error exporting submissions. Please try again.');
            }
        }

        // ===============================
        // SCANNED EXAM UPLOAD (OCR)
        // ===============================

        function showScanUpload() {
            document.getElementById('scan-upload-area').classList.remove('hidden');
            document.getElementById('scan-file-input').value = '';
            document.getElementById('scan-file-count').textContent = '';
            document.getElementById('scan-upload-progress').classList.add('hidden');
            document.getElementById('scan-upload-results').classList.add('hidden');
            document.getElementById('scan-upload-results').innerHTML = '';
            lucide.createIcons();
        }

        function hideScanUpload() {
            document.getElementById('scan-upload-area').classList.add('hidden');
        }

        async function handleScanFiles(files) {
            if (!files || files.length === 0) return;
            if (!currentQuizSessionId) {
                alert('Please select a quiz session first');
                return;
            }

            const fileCount = files.length;
            document.getElementById('scan-file-count').textContent = `${fileCount} file${fileCount > 1 ? 's' : ''} selected`;
            document.getElementById('scan-upload-progress').classList.remove('hidden');
            document.getElementById('scan-upload-results').classList.remove('hidden');
            document.getElementById('scan-upload-results').innerHTML = '';

            let processed = 0;
            let successful = 0;

            for (const file of files) {
                document.getElementById('scan-progress-text').textContent = `Processing ${processed + 1} of ${fileCount}: ${file.name}...`;

                try {
                    const formData = new FormData();
                    formData.append('pdf_file', file);
                    formData.append('quiz_session', currentQuizSessionId);

                    const response = await fetch('/api/quizzes/scan/upload/', {
                        method: 'POST',
                        headers: {
                            'X-CSRFToken': getCookie('csrftoken')
                        },
                        body: formData
                    });

                    const result = await response.json();

                    if (result.success) {
                        successful++;
                        const sub = result.submission;
                        addScanResult(file.name, 'success',
                            `${sub.student_name || 'Unknown'} - ${sub.total_points_earned}/${sub.total_points_possible} pts`);
                    } else {
                        addScanResult(file.name, 'error', result.error || 'Unknown error');
                    }
                } catch (err) {
                    console.error('Error uploading scan:', err);
                    addScanResult(file.name, 'error', err.message || 'Upload failed');
                }

                processed++;
            }

            document.getElementById('scan-upload-progress').classList.add('hidden');
            document.getElementById('scan-progress-text').textContent = `Done! ${successful} of ${fileCount} processed successfully.`;
            document.getElementById('scan-upload-progress').classList.remove('hidden');
            document.querySelector('#scan-upload-progress .animate-spin')?.classList.add('hidden');

            // Refresh submissions list
            if (currentQuizSessionId) {
                const quizName = document.getElementById('submissions-quiz-name').textContent.replace('Submissions: ', '');
                viewSubmissions(currentQuizSessionId, quizName);
            }
        }

        function addScanResult(filename, status, message) {
            const container = document.getElementById('scan-upload-results');
            const statusClass = status === 'success'
                ? 'bg-emerald-100 dark:bg-emerald-900/50 text-emerald-700 dark:text-emerald-300'
                : 'bg-red-100 dark:bg-red-900/50 text-red-700 dark:text-red-300';
            const icon = status === 'success' ? 'check-circle' : 'x-circle';

            container.innerHTML += `
                <div class="flex items-center gap-2 text-sm ${statusClass} px-3 py-2 rounded-lg">
                    <i data-lucide="${icon}" class="w-4 h-4 flex-shrink-0"></i>
                    <span class="font-medium">${escapeHtml(filename)}:</span>
                    <span>${escapeHtml(message)}</span>
                </div>
            `;
            lucide.createIcons();
        }