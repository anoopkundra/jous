// Adapted from shadcn/ui Textarea (MIT, Copyright 2023 shadcn).
import * as React from "react";
import { cn } from "@/lib/utils";
export function Textarea({ className, ...props }: React.ComponentProps<"textarea">) { return <textarea className={cn("flex min-h-28 w-full resize-y rounded-lg border border-slate-300 bg-white p-3 text-sm outline-none focus-visible:ring-2 focus-visible:ring-teal-700 disabled:opacity-50", className)} {...props} />; }
