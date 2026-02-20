import { create } from "zustand";

interface ThreadStoreState {
  activeThreadId: string | null;
  setActiveThread: (threadId: string | null) => void;
}

export const useThreadStore = create<ThreadStoreState>((set) => ({
  activeThreadId: null,
  setActiveThread: (threadId) => set({ activeThreadId: threadId }),
}));
