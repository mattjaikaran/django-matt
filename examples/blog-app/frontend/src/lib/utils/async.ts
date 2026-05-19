/**
 * Async utility functions
 */

export function sleep(ms: number): Promise<void> {
  return new Promise(resolve => setTimeout(resolve, ms));
}

export function timeout<T>(promise: Promise<T>, ms: number): Promise<T> {
  return Promise.race([
    promise,
    new Promise<never>((_, reject) =>
      setTimeout(() => reject(new Error('Operation timed out')), ms)
    ),
  ]);
}

export async function retry<T>(
  fn: () => Promise<T>,
  options: {
    retries?: number;
    delay?: number;
    backoff?: 'linear' | 'exponential';
    shouldRetry?: (error: unknown) => boolean;
  } = {}
): Promise<T> {
  const {
    retries = 3,
    delay = 1000,
    backoff = 'linear',
    shouldRetry = () => true,
  } = options;

  let lastError: unknown;

  for (let attempt = 0; attempt <= retries; attempt++) {
    try {
      return await fn();
    } catch (error) {
      lastError = error;

      if (attempt === retries || !shouldRetry(error)) {
        throw error;
      }

      const waitTime =
        backoff === 'exponential'
          ? delay * Math.pow(2, attempt)
          : delay * (attempt + 1);

      await sleep(waitTime);
    }
  }

  throw lastError;
}

export async function parallel<T>(
  promises: Promise<T>[],
  concurrency = Infinity
): Promise<T[]> {
  if (concurrency >= promises.length) {
    return Promise.all(promises);
  }

  const results: T[] = [];
  let index = 0;

  async function runNext(): Promise<void> {
    const currentIndex = index++;
    if (currentIndex >= promises.length) return;

    results[currentIndex] = await promises[currentIndex];

    await runNext();
  }

  const workers = Array(concurrency)
    .fill(null)
    .map(() => runNext());
  await Promise.all(workers);

  return results;
}

export async function series<T>(promises: (() => Promise<T>)[]): Promise<T[]> {
  const results: T[] = [];

  for (const promiseFn of promises) {
    results.push(await promiseFn());
  }

  return results;
}

export async function waterfall<T>(
  tasks: Array<(prev: T | undefined) => Promise<T>>
): Promise<T> {
  let result: T | undefined;

  for (const task of tasks) {
    result = await task(result);
  }

  return result as T;
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
type AsyncFunction = (...args: any[]) => Promise<unknown>;

export function debounceAsync<T extends AsyncFunction>(fn: T, wait: number): T {
  let timeout: ReturnType<typeof setTimeout>;
  let resolvePromise: ((value: unknown) => void) | null = null;
  let rejectPromise: ((reason: unknown) => void) | null = null;

  return ((...args: Parameters<T>) => {
    return new Promise((resolve, reject) => {
      clearTimeout(timeout);
      resolvePromise = resolve;
      rejectPromise = reject;

      timeout = setTimeout(async () => {
        try {
          const result = await fn(...args);
          resolvePromise?.(result);
        } catch (error) {
          rejectPromise?.(error);
        }
      }, wait);
    });
  }) as T;
}

export function throttleAsync<T extends AsyncFunction>(fn: T, wait: number): T {
  let lastCall = 0;
  let timeout: ReturnType<typeof setTimeout>;

  return ((...args: Parameters<T>) => {
    return new Promise((resolve, reject) => {
      const now = Date.now();
      const timeSinceLastCall = now - lastCall;

      if (timeSinceLastCall >= wait) {
        lastCall = now;
        fn(...args)
          .then(resolve)
          .catch(reject);
      } else {
        clearTimeout(timeout);
        timeout = setTimeout(() => {
          lastCall = Date.now();
          fn(...args)
            .then(resolve)
            .catch(reject);
        }, wait - timeSinceLastCall);
      }
    });
  }) as T;
}

export async function poll<T>(
  fn: () => Promise<T>,
  condition: (result: T) => boolean,
  options: {
    interval?: number;
    timeout?: number;
    maxAttempts?: number;
  } = {}
): Promise<T> {
  const { interval = 1000, timeout = 30000, maxAttempts = Infinity } = options;

  const startTime = Date.now();
  let attempts = 0;

  while (attempts < maxAttempts) {
    if (Date.now() - startTime > timeout) {
      throw new Error('Polling timeout exceeded');
    }

    try {
      const result = await fn();
      if (condition(result)) {
        return result;
      }
    } catch {
      // Continue polling on error
    }

    attempts++;
    await sleep(interval);
  }

  throw new Error('Maximum polling attempts exceeded');
}

export class AsyncQueue<T> {
  private queue: Array<() => Promise<T>> = [];
  private concurrency: number;
  private activeCount = 0;

  constructor(concurrency = 1) {
    this.concurrency = concurrency;
  }

  add(task: () => Promise<T>): Promise<T> {
    return new Promise((resolve, reject) => {
      this.queue.push(async () => {
        try {
          const result = await task();
          resolve(result);
          return result;
        } catch (error) {
          reject(error);
          throw error;
        }
      });

      this.process();
    });
  }

  private async process(): Promise<void> {
    if (this.activeCount >= this.concurrency || this.queue.length === 0) {
      return;
    }

    this.activeCount++;
    const task = this.queue.shift()!;

    try {
      await task();
    } finally {
      this.activeCount--;
      this.process();
    }
  }

  get size(): number {
    return this.queue.length;
  }

  get pending(): number {
    return this.activeCount;
  }
}
