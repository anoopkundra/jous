// Adapted from shadcn/ui Card (MIT, Copyright 2023 shadcn).
import * as React from "react";
import { cn } from "@/lib/utils";
export function Card({ className, ...props }: React.ComponentProps<"section">) { return <section className={cn("rounded-2xl border border-slate-200 bg-white p-6 shadow-sm", className)} {...props} />; }
