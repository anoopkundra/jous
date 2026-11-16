// Adapted from shadcn/ui Input (MIT, Copyright 2023 shadcn).
import * as React from "react";
import { cn } from "@/lib/utils";
export function Input({ className, ...props }: React.ComponentProps<"input">) { return <input className={cn("flex h-11 w-full rounded-lg border border-slate-300 bg-white px-3 text-sm outline-none focus-visible:ring-2 focus-visible:ring-teal-700 disabled:opacity-50 aria-invalid:border-red-600", className)} {...props} />; }
