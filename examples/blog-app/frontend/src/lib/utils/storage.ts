/**
 * Local storage utility functions with error handling and type safety
 */

export class StorageManager {
  private static isStorageAvailable(
    type: 'localStorage' | 'sessionStorage'
  ): boolean {
    try {
      const storage = window[type];
      const test = '__storage_test__';
      storage.setItem(test, test);
      storage.removeItem(test);
      return true;
    } catch {
      return false;
    }
  }

  static setItem<T>(key: string, value: T, useSession = false): boolean {
    const storage = useSession ? 'sessionStorage' : 'localStorage';

    if (!this.isStorageAvailable(storage)) {
      console.warn(`${storage} is not available`);
      return false;
    }

    try {
      const serializedValue = JSON.stringify(value);
      window[storage].setItem(key, serializedValue);
      return true;
    } catch (error) {
      console.error(`Error saving to ${storage}:`, error);
      return false;
    }
  }

  static getItem<T>(key: string, defaultValue: T, useSession = false): T {
    const storage = useSession ? 'sessionStorage' : 'localStorage';

    if (!this.isStorageAvailable(storage)) {
      return defaultValue;
    }

    try {
      const item = window[storage].getItem(key);
      if (item === null) {
        return defaultValue;
      }
      return JSON.parse(item) as T;
    } catch (error) {
      console.error(`Error reading from ${storage}:`, error);
      return defaultValue;
    }
  }

  static removeItem(key: string, useSession = false): boolean {
    const storage = useSession ? 'sessionStorage' : 'localStorage';

    if (!this.isStorageAvailable(storage)) {
      return false;
    }

    try {
      window[storage].removeItem(key);
      return true;
    } catch (error) {
      console.error(`Error removing from ${storage}:`, error);
      return false;
    }
  }

  static clear(useSession = false): boolean {
    const storage = useSession ? 'sessionStorage' : 'localStorage';

    if (!this.isStorageAvailable(storage)) {
      return false;
    }

    try {
      window[storage].clear();
      return true;
    } catch (error) {
      console.error(`Error clearing ${storage}:`, error);
      return false;
    }
  }

  static getAllKeys(useSession = false): string[] {
    const storage = useSession ? 'sessionStorage' : 'localStorage';

    if (!this.isStorageAvailable(storage)) {
      return [];
    }

    try {
      return Object.keys(window[storage]);
    } catch (error) {
      console.error(`Error getting keys from ${storage}:`, error);
      return [];
    }
  }

  static getSize(useSession = false): number {
    const storage = useSession ? 'sessionStorage' : 'localStorage';

    if (!this.isStorageAvailable(storage)) {
      return 0;
    }

    try {
      let total = 0;
      for (const key in window[storage]) {
        if (Object.prototype.hasOwnProperty.call(window[storage], key)) {
          total += window[storage][key].length + key.length;
        }
      }
      return total;
    } catch (error) {
      console.error(`Error calculating ${storage} size:`, error);
      return 0;
    }
  }
}

// Convenience functions for common use cases
export const localStorage = {
  set: <T>(key: string, value: T) => StorageManager.setItem(key, value, false),
  get: <T>(key: string, defaultValue: T) =>
    StorageManager.getItem(key, defaultValue, false),
  remove: (key: string) => StorageManager.removeItem(key, false),
  clear: () => StorageManager.clear(false),
  keys: () => StorageManager.getAllKeys(false),
  size: () => StorageManager.getSize(false),
};

export const sessionStorage = {
  set: <T>(key: string, value: T) => StorageManager.setItem(key, value, true),
  get: <T>(key: string, defaultValue: T) =>
    StorageManager.getItem(key, defaultValue, true),
  remove: (key: string) => StorageManager.removeItem(key, true),
  clear: () => StorageManager.clear(true),
  keys: () => StorageManager.getAllKeys(true),
  size: () => StorageManager.getSize(true),
};
