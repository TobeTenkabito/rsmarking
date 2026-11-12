export const agentEnvironment = `
    <dialog id="ai-environment-dialog" aria-labelledby="ai-environment-title">
        <form id="ai-environment-form" autocomplete="off">
            <header>
                <div>
                    <h2 id="ai-environment-title">Agent environment</h2>
                    <p id="ai-environment-source"></p>
                </div>
                <button type="button" data-environment-close aria-label="Close">×</button>
            </header>
            <p class="ai-environment-note">Configure the provider used by the next AI request. Running tasks keep their current configuration.</p>
            <fieldset id="ai-environment-fields" disabled>
                <label>
                    Model provider
                    <select id="ai-environment-provider" required></select>
                </label>
                <label>
                    Model ID
                    <input id="ai-environment-model" required maxlength="200" spellcheck="false">
                </label>
                <label>
                    API base URL
                    <input id="ai-environment-base" type="url" required maxlength="1000" spellcheck="false">
                </label>
                <label>
                    API key
                    <input id="ai-environment-key" type="password" autocomplete="new-password" maxlength="8192" spellcheck="false">
                </label>
                <p id="ai-environment-key-hint" class="ai-environment-note"></p>
                <details>
                    <summary>Advanced options</summary>
                    <div class="ai-environment-grid">
                        <label>
                            Request timeout (seconds)
                            <input id="ai-environment-timeout" type="number" min="1" max="600" value="90" required>
                        </label>
                        <label>
                            Maximum output tokens
                            <input id="ai-environment-tokens" type="number" min="128" max="131072" value="4096" required>
                        </label>
                        <label>
                            Tool reasoning effort
                            <select id="ai-environment-reasoning">
                                <option value>Provider default</option>
                                <option value="none">none</option>
                                <option value="minimal">minimal</option>
                                <option value="low">low</option>
                                <option value="medium">medium</option>
                                <option value="high">high</option>
                            </select>
                        </label>
                    </div>
                </details>
            </fieldset>
            <p class="ai-environment-note">Keys are stored only in the local gateway configuration file, never in chat history or browser storage. Protect the server storage directory.</p>
            <p id="ai-environment-status" role="status" aria-live="polite"></p>
            <footer>
                <button id="ai-environment-reset" type="button">Use .env defaults</button>
                <button id="ai-environment-save" type="submit" disabled>Save configuration</button>
            </footer>
        </form>
    </dialog>
`;

export const agentEnvironmentStyles = `
    .ai-environment-launcher {
        display: flex;
        align-items: center;
        gap: 9px;
        padding: 0 6px;
    }

    #ai-window .ai-environment-button {
        display: grid;
        place-items: center;
        border: 1px solid #d4e0d8;
        background: #e5ede9;
        color: #294e3e;
        width: 38px;
        height: 38px;
        border-radius: 50%;
        flex-shrink: 0;
        font-size: 21px;
    }

    .ai-environment-button:hover {
        box-shadow: 0 0 0 3px #dce8e1;
    }

    .ai-environment-label {
        font-size: 11px;
        color: #697d72;
    }

    #ai-environment-dialog {
        margin: auto;
        padding: 0;
        border: 1px solid #dce5df;
        border-radius: 16px;
        width: min(540px,calc(100vw - 28px));
        max-height: 90dvh;
        overflow: auto;
        color: #243247;
        background: white;
        box-shadow: 0 24px 90px #0f172a40;
        font: 14px/1.6 system-ui,sans-serif;
    }

    #ai-environment-dialog::backdrop {
        background: #0f172a66;
        backdrop-filter: blur(3px);
    }

    #ai-environment-form {
        padding: 24px;
    }

    #ai-environment-form header {
        display: flex;
        justify-content: space-between;
        align-items: start;
        gap: 12px;
        margin-bottom: 14px;
    }

    #ai-environment-form h2 {
        font-size: 18px;
        font-weight: 600;
        margin: 0;
    }

    #ai-environment-source {
        font-size: 12px;
        color: #6b8174;
        margin: 4px 0;
    }

    #ai-environment-form button {
        font: inherit;
        cursor: pointer;
        border: 1px solid #d6e1da;
        border-radius: 8px;
        background: white;
        padding: 7px 12px;
    }

    #ai-environment-form [data-environment-close] {
        border: 0;
        font-size: 24px;
        padding: 0 5px;
        color: #6d7c73;
    }

    #ai-environment-form fieldset {
        border: 0;
        padding: 0;
        margin: 0;
        min-width: 0;
    }

    #ai-environment-form label {
        display: flex;
        flex-direction: column;
        gap: 5px;
        font-size: 12px;
        margin: 12px 0;
    }

    #ai-environment-form input,#ai-environment-form select {
        box-sizing: border-box;
        min-width: 0;
        width: 100%;
        font: 14px system-ui,sans-serif;
        padding: 9px;
        border: 1px solid #d6e1da;
        border-radius: 7px;
        background: #fff;
        color: #243247;
    }

    #ai-environment-form input:focus-visible,#ai-environment-form select:focus-visible,#ai-environment-form button:focus-visible {
        outline: 2px solid #62937b;
        outline-offset: 2px;
    }

    .ai-environment-note {
        font-size: 11px;
        line-height: 1.6;
        color: #7e8a84;
        margin: 8px 0;
    }

    .ai-environment-grid {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 0 12px;
    }

    #ai-environment-form summary {
        font-size: 12px;
        cursor: pointer;
        color: #506b5b;
        margin: 14px 0 4px;
    }

    #ai-environment-form footer {
        display: flex;
        justify-content: space-between;
        gap: 10px;
        margin-top: 16px;
    }

    #ai-environment-form #ai-environment-save {
        background: #294e3e;
        color: white;
        border-color: #294e3e;
    }

    #ai-environment-form :disabled {
        opacity: .55;
        cursor: wait;
    }

    #ai-environment-status {
        font-size: 12px;
        color: #397151;
        overflow-wrap: anywhere;
        margin: 8px 0;
    }

    #ai-environment-status[data-error="true"] {
        color: #ad3428;
    }

    @media(max-width:450px) {
        .ai-environment-label {
            display: none;
        }

        #ai-environment-form {
            padding: 18px;
        }

        .ai-environment-grid {
            grid-template-columns: 1fr;
        }

    }
`;
