import { reindexMedia, buildGraph, fetchGraphData, fetchJobStatus } from '../lib/api';

// Mock global fetch
global.fetch = jest.fn();

describe('Frontend API - ETL Proxy endpoints', () => {
    beforeEach(() => {
        (global.fetch as jest.Mock).mockClear();
    });

    it('reindexMedia should call the /etl/reindex-media endpoint with correct payload', async () => {
        (global.fetch as jest.Mock).mockResolvedValue({
            ok: true,
            json: async () => ({ job_id: 'test-job', status: 'queued' }),
        });

        const result = await reindexMedia(true);

        expect(global.fetch).toHaveBeenCalledWith(
            '/etl/reindex-media?force_reindex=true',
            expect.objectContaining({
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    media_types: ["photo", "audio", "document", "voice"],
                    force_reindex: true
                })
            })
        );
        expect(result).toEqual({ job_id: 'test-job', status: 'queued' });
    });

    it('buildGraph should call the /etl/graph/build endpoint', async () => {
        (global.fetch as jest.Mock).mockResolvedValue({
            ok: true,
            json: async () => ({ nodes: [], edges: [] }),
        });

        await buildGraph(false);

        expect(global.fetch).toHaveBeenCalledWith(
            '/etl/graph/build?force_rebuild=false',
            expect.objectContaining({
                method: 'POST'
            })
        );
    });

    it('fetchGraphData should call the /etl/graph/data endpoint', async () => {
        (global.fetch as jest.Mock).mockResolvedValue({
            ok: true,
            json: async () => ({ nodes: [], edges: [] }),
        });

        await fetchGraphData();

        expect(global.fetch).toHaveBeenCalledWith(
            '/etl/graph/data'
        );
    });

    it('fetchJobStatus should call the /etl/jobs/job-id endpoint', async () => {
        (global.fetch as jest.Mock).mockResolvedValue({
            ok: true,
            json: async () => ({ job_id: 'test-job', status: 'running', progress: 0.5, message: 'Processing' }),
        });

        const result = await fetchJobStatus('test-job');

        expect(global.fetch).toHaveBeenCalledWith(
            '/etl/jobs/test-job'
        );
        expect(result).toEqual({ job_id: 'test-job', status: 'running', progress: 0.5, message: 'Processing' });
    });
});
