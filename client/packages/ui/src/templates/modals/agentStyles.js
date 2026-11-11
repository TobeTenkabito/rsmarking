export const agentStyles = `
#ai-modal {position:fixed;inset:0;z-index:2000;display:flex;align-items:center;justify-content:center;font:14px/1.6 system-ui,sans-serif;color:#243247;padding:20px;background:#0f172a66;backdrop-filter:blur(5px)}
#ai-window .hidden {display:none!important}
#ai-modal.hidden {display:none!important}
#ai-window {display:flex;flex-direction:row;width:min(1200px,97vw);height:min(850px,94dvh);min-height:0;overflow:hidden;border:1px solid #dce3ec;border-radius:18px;background:white;box-shadow:0 24px 90px #0f172a33}
#ai-window button,#ai-window select,#ai-window input,#ai-window textarea {font:inherit}
#ai-window button {cursor:pointer}#ai-window button:disabled {cursor:wait;opacity:.5}
#ai-window :focus-visible {outline:2px solid #3b82f6;outline-offset:3px}
.ai-history {width:232px;flex-shrink:0;display:flex;flex-direction:column;background:#f7f8fa;border-right:1px solid #e8ebef;padding:20px 12px;gap:14px;min-height:0}
.ai-brand {font-weight:700;letter-spacing:-.4px;padding:0 8px;display:flex;align-items:center;gap:9px}
.ai-brand-mark {background:#263c36;color:white;display:grid;place-items:center;width:28px;height:28px;border-radius:9px;font-size:11px;letter-spacing:0}
.ai-new-chat {display:flex;gap:9px;align-items:center;border:1px solid #dce3e1;border-radius:9px;background:white;padding:9px 12px;font-weight:600!important;text-align:left}
.ai-history-search {width:100%;border:1px solid #e3e7ec;border-radius:8px;background:white;padding:7px 10px;font-size:12px!important;box-sizing:border-box}
.ai-history-heading {display:flex;align-items:center;justify-content:space-between;padding:0 6px;font-size:11px;color:#778398}
.ai-history-heading {flex-wrap:wrap;gap:4px}.ai-history-heading-actions {display:flex;align-items:center;gap:4px}.ai-history-import {font-size:11px!important;border:0;background:none;color:#536b5e;padding:3px}
#ai-agent-archive-list {flex:1;min-height:0;overflow-y:auto}
.ai-history-item {display:grid;grid-template-columns:minmax(0,1fr) auto;align-items:start;border-radius:8px;margin-bottom:4px;padding-bottom:8px}.ai-history-item:hover {background:#edf0f3}.ai-history-item.active {background:#e5ede9;color:#24483b}
.ai-history-open {flex:1;min-width:0;text-align:left;padding:10px 9px;border:0;background:none}
.ai-history-open strong {display:block;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-size:12px;font-weight:500}.ai-history-open small {display:block;font-size:10px;color:#8992a0;margin-top:2px}
.ai-history-actions {display:flex;padding-top:8px}
.ai-history-delete,.ai-history-edit {border:0;background:none;color:#7b8796;padding:3px 5px;opacity:0}.ai-history-item:hover .ai-history-actions button,.ai-history-item:focus-within .ai-history-actions button {opacity:1}.ai-history-delete:hover {color:#b91c1c}.ai-history-edit:hover {color:#24483b}
.ai-history-annotation {grid-column:1/-1;display:-webkit-box;-webkit-box-orient:vertical;-webkit-line-clamp:2;overflow:hidden;overflow-wrap:anywhere;white-space:pre-wrap;text-align:left;font-size:10px!important;line-height:1.6!important;color:#6d7885;border:0;background:none;margin:0 9px 4px;padding:0}
.ai-history-annotation:hover {color:#24483b}.ai-history-annotation[aria-expanded="true"] {display:block;-webkit-line-clamp:unset}
.ai-history-date {grid-column:1/-1;font-size:10px;color:#8992a0;padding:0 9px}
.ai-history-editor {grid-column:1/-1;min-width:0;padding:8px;display:flex;flex-direction:column;gap:6px}.ai-history-editor label {font-size:11px;color:#65736b}
#ai-window .ai-history-editor input,#ai-window .ai-history-editor textarea {box-sizing:border-box;width:100%;min-width:0;border:1px solid #cbd8d0;border-radius:6px;padding:6px;background:white;font-size:12px;resize:vertical}
.ai-history-edit-actions {display:flex;justify-content:flex-end;gap:6px;flex-wrap:wrap}.ai-history-edit-actions button {font-size:11px!important;border:1px solid #d4ded8;border-radius:6px;padding:4px 8px;background:white}.ai-history-edit-actions button[type="submit"] {background:#294e3e;color:white;border-color:#294e3e}
.ai-history-edit-error {font-size:11px;color:#ad3428;overflow-wrap:anywhere}
.ai-history-more {border:0;background:none;color:#7b8796;padding:3px 5px;opacity:0}.ai-history-more[aria-expanded="true"] {opacity:1}
.ai-history-menu {grid-column:1/-1;display:flex;flex-direction:column;border-top:1px solid #dce4df;margin:6px 7px 0;padding-top:5px;gap:2px}.ai-history-menu button {border:0;background:transparent;text-align:left;font-size:11px!important;padding:5px;border-radius:4px;color:#42584b}.ai-history-menu button:hover {background:#dce6df}.ai-history-menu [data-ai-delete-chat] {color:#a9443d}
.ai-history-pin {color:#39765a;font-weight:600}.ai-message-actions {display:flex;gap:16px;flex-wrap:wrap}
@media(hover:none) {.ai-history-actions button {opacity:1}}
.ai-history-note {font-size:11px;color:#8b95a3;line-height:1.7;padding:0 6px}
.ai-main {min-width:0;flex:1;display:flex;flex-direction:column;position:relative}
.ai-header {display:flex;align-items:center;justify-content:space-between;gap:12px;border-bottom:1px solid #eef0f3;padding:14px 24px;flex-shrink:0}.ai-header h2 {font-size:14px;font-weight:600;margin:0}
.ai-caption {font-size:11px;color:#8994a5}.ai-header-actions {display:flex;align-items:center;gap:8px}
.ai-icon-button {border:0;background:transparent;color:#6b7788;border-radius:7px;padding:5px 9px;font-size:18px!important}.ai-icon-button:hover {background:#f1f4f6}
.ai-settings summary {list-style:none;cursor:pointer;font-size:12px;color:#687588;border:1px solid #e3e7ec;border-radius:8px;padding:5px 10px}.ai-settings {position:relative}
.ai-settings-card {position:absolute;right:0;top:38px;width:min(360px,80vw);max-height:65dvh;overflow:auto;z-index:60;background:white;border:1px solid #e1e6ed;border-radius:12px;padding:18px;box-shadow:0 12px 40px #0f172a22}
.ai-setting {display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:14px;font-size:12px}.ai-setting select {max-width:200px;min-width:130px;border:1px solid #dce2e9;background:#fff;border-radius:6px;padding:5px}
.ai-setting-note {font-size:11px;color:#8791a0;margin:-6px 0 14px;line-height:1.6}.ai-setting-check {display:flex;align-items:center;gap:8px;font-size:12px;margin:12px 0}
.ai-body {position:relative;min-height:0;flex:1;overflow:hidden}#ai-agent-panel {height:100%;display:flex;flex-direction:column}#ai-agent-panel.hidden {display:none}
#ai-agent-messages {min-height:0;flex:1;overflow:auto;scrollbar-gutter:stable;padding:28px max(24px,calc((100% - 760px)/2));overscroll-behavior:contain}
.ai-empty {min-height:90%;display:flex;flex-direction:column;align-items:center;justify-content:center;text-align:center;padding:30px 12px}.ai-empty h3 {font-size:26px;font-weight:600;letter-spacing:-.7px;color:#2c433b;margin:16px 0 8px}.ai-empty p {font-size:13px;color:#85908e;max-width:380px;margin:0 0 26px}
.ai-suggestions {display:flex;flex-wrap:wrap;justify-content:center;gap:8px}.ai-suggestions button {border:1px solid #e3e9e6;border-radius:9px;background:#fafcfb;padding:10px 14px;font-size:12px!important;color:#53675e}
.ai-message {margin-bottom:26px;max-width:100%;min-width:0}.ai-message-user {display:flex;justify-content:flex-end}.ai-message-user .ai-bubble {background:#eef3f0;border-radius:14px 14px 3px 14px;max-width:85%;padding:12px 16px;color:#33483f}
.ai-message-assistant .ai-bubble {max-width:100%;padding:0 4px}.ai-message-label {font-size:11px;font-weight:600;color:#6a8175;margin-bottom:8px;letter-spacing:.3px}.ai-message-error {color:#b42318;background:#fef3f2;border-radius:10px;padding:14px}
.ai-message-copy {border:0;background:none;font-size:11px!important;color:#9aa3af;padding:5px 0;margin-top:6px}
.ai-markdown {overflow-wrap:anywhere;line-height:1.8;font-size:14px;color:inherit}.ai-markdown > :first-child {margin-top:0}.ai-markdown > :last-child {margin-bottom:0}
.ai-markdown p {margin:0 0 12px}.ai-markdown h1,.ai-markdown h2,.ai-markdown h3,.ai-markdown h4,.ai-markdown h5,.ai-markdown h6 {font-weight:650;line-height:1.4;margin:24px 0 12px}.ai-markdown h1 {font-size:23px}.ai-markdown h2 {font-size:20px}.ai-markdown h3 {font-size:17px}
.ai-markdown ul,.ai-markdown ol {padding-left:24px;margin:10px 0;list-style-position:outside}.ai-markdown ul {list-style-type:disc}.ai-markdown ol {list-style-type:decimal}.ai-markdown li {margin:4px 0}.ai-markdown li > p {margin:4px 0}.ai-markdown li ul,.ai-markdown li ol {margin:4px 0}
.ai-markdown blockquote {border-left:3px solid #b2c7bc;padding:4px 16px;color:#697d72;background:#f7faf8;margin:14px 0}
.ai-markdown code {background:#eef1f4;border-radius:4px;padding:2px 5px;font:12px/1.6 ui-monospace,Consolas,monospace;color:#496270}.ai-markdown pre {overflow-x:auto;max-width:100%;background:#17232b;color:#e0e8ed;border-radius:10px;padding:16px;margin:16px 0;white-space:pre}.ai-markdown pre code {padding:0;background:none;color:inherit;font-size:12px}
.ai-markdown a {color:#24775e;text-decoration:underline;text-underline-offset:3px}.ai-markdown table {display:block;max-width:100%;overflow-x:auto;border-collapse:collapse;margin:16px 0;font-size:12px}.ai-markdown th,.ai-markdown td {border:1px solid #dde5e1;padding:8px 12px;text-align:left}.ai-markdown th {background:#f3f7f4;font-weight:600}.ai-markdown hr {border:0;border-top:1px solid #e3e9e6;margin:20px 0}
.ai-tool-trace {margin-top:12px;font-size:11px;color:#778497}.ai-tool-trace summary {cursor:pointer}
.ai-composer {flex-shrink:0;padding:12px max(20px,calc((100% - 800px)/2)) 16px;background:white}.ai-composer-box {border:1px solid #dce4e0;border-radius:14px;padding:12px 14px;box-shadow:0 2px 10px #243c2e06}.ai-composer-box:focus-within {border-color:#9bb9a9;box-shadow:0 0 0 3px #eaf2ed}
#ai-prompt-input {display:block;width:100%;resize:none;min-height:48px;max-height:180px;background:transparent;border:0;outline:0;font-size:14px;line-height:1.6;padding:0;box-shadow:none}#ai-prompt-input:focus-visible {outline:0}
.ai-composer-controls {display:flex;justify-content:space-between;align-items:center;margin-top:8px;gap:8px}.ai-composer-left {display:flex;align-items:center;gap:10px;font-size:11px;color:#8c97a0}
#ai-execute-btn {border:0;background:#294e3e;color:white;border-radius:9px;padding:7px 16px;display:flex;gap:7px;align-items:center;font-size:12px}#ai-execute-btn:hover {background:#1d3f30}
.ai-composer-footer {display:flex;justify-content:space-between;align-items:center;gap:8px;font-size:10px;color:#98a19d;padding-top:8px}#ai-send-mode {border:0;background:transparent;color:#819087;font-size:10px!important;max-width:210px}
.ai-status {font-size:11px;color:#87958d;border:0;background:none;text-align:left;padding:0}.ai-toast {padding:8px 20px;font-size:12px}.ai-toast.hidden {display:none}#ai-error-msg {background:#fff3f1;color:#ad3428}#ai-success-msg {background:#eff8f2;color:#397151}
#ai-result-section {height:100%;overflow:auto;padding:24px}#ai-result-section.hidden {display:none}#ai-result-content {white-space:pre-wrap}.ai-result-markdown {white-space:normal!important}
@media(max-width:700px) {#ai-modal {padding:0}#ai-window {width:100vw;height:100dvh;border-radius:0;border:0}.ai-history {width:170px;padding:14px 8px}.ai-header {padding:12px}.ai-header h2 {font-size:12px}#ai-agent-messages {padding:20px 14px}.ai-composer {padding:10px}.ai-empty h3 {font-size:21px}.ai-history-delete {opacity:1}.ai-composer-footer {flex-wrap:wrap}}
@media(max-width:450px) {.ai-history {width:124px}.ai-brand {font-size:11px;padding:0}.ai-brand-mark {display:none}.ai-new-chat {font-size:11px!important;padding:7px}.ai-history-search {font-size:10px!important}.ai-history-heading {font-size:10px}.ai-caption {display:none}.ai-header-actions {gap:2px}.ai-settings summary {font-size:11px;padding:4px 6px}.ai-history-open {padding:9px 4px}.ai-history-open strong {font-size:11px}.ai-history-delete {padding:3px}.ai-history-note {display:none}.ai-empty {padding:10px 0}.ai-suggestions button {padding:7px;font-size:11px!important}}
`;
