import { it, expect, vi } from 'vitest';
import { GlobalEvents } from '@app/core/GlobalEvents.js';
import { Store } from '@app/store/index.js';

it('typing and dialog shortcuts never delete the selected map feature', async () => {
    const handleDeleteSelectedFeature = vi.fn();
    const events = new GlobalEvents({ project: { handleDeleteSelectedFeature } });
    // Capture the real handler and remove it after the test.
    const add = vi.spyOn(document, 'addEventListener');
    events.bindKeyboardEvents();
    const listener = add.mock.calls.find(([type]) => type === 'keydown')[1];
    const previous = Store.state.selectedFeatureId;
    Store.state.selectedFeatureId = 'feature-1';
    try {
        document.body.innerHTML = '<textarea></textarea><div contenteditable="true"></div><section role="dialog"><button>Chat</button></section><div id="map"></div>';
        for (const selector of ['textarea', '[contenteditable]', 'button']) {
            document.querySelector(selector).dispatchEvent(new KeyboardEvent('keydown', { key: 'Backspace', bubbles: true }));
            document.querySelector(selector).dispatchEvent(new KeyboardEvent('keydown', { key: 'Delete', bubbles: true }));
        }
        expect(handleDeleteSelectedFeature).not.toHaveBeenCalled();
        document.querySelector('#map').dispatchEvent(new KeyboardEvent('keydown', { key: 'Delete', bubbles: true }));
        expect(handleDeleteSelectedFeature).toHaveBeenCalledTimes(1);
    } finally {
        document.removeEventListener('keydown', listener);
        add.mockRestore(); Store.state.selectedFeatureId = previous; document.body.innerHTML = '';
    }
});
