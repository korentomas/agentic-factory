import type { Metadata } from "next";
import React from "react";

export const metadata: Metadata = {
  title: "Task — LailaTov",
  description: "Task execution view",
};

export default function ThreadLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
