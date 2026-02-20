import { ThreadView } from "@/components/v2/thread-view";

export default async function ThreadPage({
  params,
}: {
  params: Promise<{ thread_id: string }>;
}) {
  const { thread_id } = await params;
  return <ThreadView threadId={thread_id} />;
}
