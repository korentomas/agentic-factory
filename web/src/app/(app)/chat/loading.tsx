import { Skeleton } from "@/components/ui/skeleton";

export default function ChatLoading() {
  return (
    <div className="bg-background flex h-screen flex-col">
      {/* Header skeleton */}
      <div className="border-border border-b px-4 py-2">
        <div className="flex items-center gap-3">
          <Skeleton className="h-6 w-6 rounded" />
          <Skeleton className="h-5 w-24" />
          <div className="ml-auto flex items-center gap-2">
            <Skeleton className="h-6 w-6 rounded" />
            <Skeleton className="h-6 w-6 rounded" />
          </div>
        </div>
      </div>
      {/* Content skeleton */}
      <div className="mx-auto w-full max-w-4xl space-y-6 p-4 pt-12">
        <Skeleton className="h-48 w-full rounded-md" />
        <div className="grid gap-3 md:grid-cols-2">
          <Skeleton className="h-28 rounded-md" />
          <Skeleton className="h-28 rounded-md" />
          <Skeleton className="h-28 rounded-md" />
          <Skeleton className="h-28 rounded-md" />
        </div>
      </div>
    </div>
  );
}
