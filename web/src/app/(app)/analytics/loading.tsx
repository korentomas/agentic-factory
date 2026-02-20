import { Skeleton } from "@/components/ui/skeleton";

export default function AnalyticsLoading() {
  return (
    <div className="flex min-h-screen flex-col bg-background">
      {/* Header skeleton */}
      <div className="border-b border-border bg-card px-4 py-2">
        <div className="flex items-center gap-3">
          <Skeleton className="h-6 w-6 rounded" />
          <Skeleton className="h-5 w-24" />
          <div className="hidden items-center gap-2 md:flex">
            <Skeleton className="h-5 w-14 rounded-md" />
            <Skeleton className="h-5 w-16 rounded-md" />
            <Skeleton className="h-5 w-18 rounded-md" />
            <Skeleton className="h-5 w-16 rounded-md" />
          </div>
          <div className="ml-auto flex items-center gap-2">
            <Skeleton className="h-6 w-6 rounded" />
            <Skeleton className="h-6 w-6 rounded-full" />
          </div>
        </div>
      </div>

      {/* Content */}
      <main className="mx-auto w-full max-w-7xl px-6 py-8">
        {/* Title */}
        <div className="mb-8">
          <Skeleton className="h-9 w-80" />
          <Skeleton className="mt-2 h-5 w-64" />
        </div>

        {/* Stats cards */}
        <div className="mb-8 grid grid-cols-2 gap-4 lg:grid-cols-4">
          <Skeleton className="h-24 rounded-lg" />
          <Skeleton className="h-24 rounded-lg" />
          <Skeleton className="h-24 rounded-lg" />
          <Skeleton className="h-24 rounded-lg" />
        </div>

        {/* Tabs */}
        <Skeleton className="mb-6 h-10 w-96 rounded-lg" />

        {/* Content area */}
        <div className="space-y-6">
          <Skeleton className="h-64 rounded-lg" />
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            <Skeleton className="h-48 rounded-lg" />
            <Skeleton className="h-48 rounded-lg" />
          </div>
        </div>
      </main>
    </div>
  );
}
