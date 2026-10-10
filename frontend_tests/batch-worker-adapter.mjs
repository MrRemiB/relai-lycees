import {parentPort} from 'node:worker_threads';
globalThis.self={postMessage:data=>parentPort.postMessage(data)};
await import('../static/batch-worker.js');
parentPort.on('message',data=>self.onmessage({data}));
