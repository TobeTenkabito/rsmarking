import { afterEach, describe, expect, it, vi } from 'vitest';
import { AIAPI } from '../../../../client/packages/app/src/api/ai.js';
import { AIModule } from '../../../../client/packages/app/src/modules/AIModule.js';

describe('Agent live progress', () => {
    afterEach(() => {
        vi.restoreAllMocks();
        vi.useRealTimers();
    });

    it('polls the active request and stops timers and in-flight requests on completion', async () => {
        vi.useFakeTimers();
        const module = new AIModule({});
        module._sessionId = 'chat';
        module._renderAgentConversation = vi.fn();
        const message = { pending: true };
        const progress = { request_id: 'request', stage: 'executing', phase: 'tool', tool: 'run_script_sandbox' };
        const poll = vi.spyOn(AIAPI, 'agentProgress').mockResolvedValue(progress);
        const stop = module._startAgentProgress({ session_id: 'chat', request_id: 'request' }, message);
        await vi.advanceTimersByTimeAsync(1100);
        expect(message.progress).toEqual(progress);
        expect(message.elapsedSeconds).toBe(1);
        const signal = poll.mock.calls[0][2];
        stop();
        expect(signal.aborted).toBe(true);
        await vi.advanceTimersByTimeAsync(10000);
        expect(poll).toHaveBeenCalledTimes(1);
        expect(vi.getTimerCount()).toBe(0);
    });

    it('ignores a different request and survives an unavailable progress endpoint', async () => {
        vi.useFakeTimers();
        const module = new AIModule({});
        module._sessionId = 'chat';
        module._renderAgentConversation = vi.fn();
        const message = { pending: true };
        vi.spyOn(AIAPI, 'agentProgress')
            .mockResolvedValueOnce({ request_id: 'stale', stage: 'reviewing' })
            .mockRejectedValueOnce(new Error('offline'));
        const stop = module._startAgentProgress({ session_id: 'chat', request_id: 'request' }, message);
        await vi.advanceTimersByTimeAsync(3000);
        expect(message.progress).toBeUndefined();
        expect(message.pending).toBe(true);
        stop();
    });

    it('shows the current operation and escapes model-supplied task titles', () => {
        const module = new AIModule({});
        const html = module._renderPendingAgentMessage({ elapsedSeconds: 8, progress: {
            stage: 'executing', phase: 'tool', tool: 'run_script_sandbox',
            task_title: '<img src=x onerror=alert(1)>', total_tasks: 2, completed_tasks: 1,
        } });
        expect(html).toContain('run_script_sandbox');
        expect(html).toContain('1/2');
        expect(html).toContain('8s');
        expect(html).not.toContain('<img');
    });
});
