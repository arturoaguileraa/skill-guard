import { Link } from "@tanstack/react-router";

import { ModeToggle } from "./mode-toggle";

const NAV = [
	{ to: "/", label: "Tester" },
	{ to: "/why", label: "Why" },
	{ to: "/hub", label: "Hub" },
] as const;

export default function Header() {
	return (
		<header className="sticky top-0 z-30 border-border border-b bg-background/70 backdrop-blur-md">
			<div className="mx-auto flex h-14 w-full max-w-6xl items-center justify-between gap-4 px-5">
				<Link
					to="/"
					className="group flex items-center gap-2.5 outline-none"
					aria-label="skillguard home"
				>
					<span className="flex size-7 items-center justify-center rounded-[--radius] bg-foreground font-display text-background text-sm transition-transform group-hover:-translate-y-px">
						s
					</span>
					<span className="font-display text-[15px] tracking-tight">
						skillguard
					</span>
				</Link>

				<nav className="flex items-center gap-1">
					{NAV.map((item) => (
						<Link
							key={item.to}
							to={item.to}
							activeOptions={{ exact: item.to === "/" }}
							className="rounded-[--radius] px-2.5 py-1.5 font-mono text-muted-foreground text-xs transition-colors hover:text-foreground data-[status=active]:text-foreground"
						>
							{item.label}
						</Link>
					))}
					<span className="mx-1 hidden h-4 w-px bg-border sm:block" />
					<ModeToggle />
				</nav>
			</div>
		</header>
	);
}
