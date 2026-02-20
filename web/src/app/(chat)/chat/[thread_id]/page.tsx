"use client";

import { use } from "react";
import { ThreadView } from "@/components/v2/thread-view";

interface ThreadPageProps {
  thread_id: string;
}

export default function ThreadPage({
  params,
}: {
  params: Promise<ThreadPageProps>;
}) {
  const { thread_id } = use(params);

  return <ThreadView threadId={thread_id} />;
}
