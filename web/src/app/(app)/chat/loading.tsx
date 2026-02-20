import { Skeleton } from "@/components/ui/skeleton";
import { AppHeader } from "@/components/v2/app-header";

export default function ChatLoading() {
  return (
    <div className="bg-background flex h-screen flex-col">
      <AppHeader showBrand />

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
