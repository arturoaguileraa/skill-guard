import { type HTMLMotionProps, motion, useReducedMotion } from "motion/react";
import type { ReactNode } from "react";

/** Expo-out — the calm, fast-in/slow-settle easing behind most polished sites. */
export const EASE_OUT = [0.16, 1, 0.3, 1] as const;

type RevealProps = {
	children: ReactNode;
	delay?: number;
	y?: number;
	className?: string;
	once?: boolean;
} & Omit<HTMLMotionProps<"div">, "children">;

/** Fade + rise into view on scroll. Disabled under prefers-reduced-motion. */
export function Reveal({
	children,
	delay = 0,
	y = 16,
	className,
	once = true,
	...props
}: RevealProps) {
	const reduce = useReducedMotion();
	return (
		<motion.div
			className={className}
			initial={reduce ? false : { opacity: 0, y }}
			whileInView={reduce ? undefined : { opacity: 1, y: 0 }}
			viewport={{ once, margin: "-10% 0px -10% 0px" }}
			transition={{ duration: 0.7, ease: EASE_OUT, delay }}
			{...props}
		>
			{children}
		</motion.div>
	);
}

/** Container that staggers its <StaggerItem> children as the group enters view. */
export function Stagger({
	children,
	className,
	gap = 0.06,
	once = true,
}: {
	children: ReactNode;
	className?: string;
	gap?: number;
	once?: boolean;
}) {
	return (
		<motion.div
			className={className}
			initial="hidden"
			whileInView="show"
			viewport={{ once, margin: "-10% 0px -10% 0px" }}
			variants={{
				hidden: {},
				show: { transition: { staggerChildren: gap } },
			}}
		>
			{children}
		</motion.div>
	);
}

export function StaggerItem({
	children,
	className,
	y = 14,
}: {
	children: ReactNode;
	className?: string;
	y?: number;
}) {
	const reduce = useReducedMotion();
	return (
		<motion.div
			className={className}
			variants={{
				hidden: reduce ? {} : { opacity: 0, y },
				show: {
					opacity: 1,
					y: 0,
					transition: { duration: 0.6, ease: EASE_OUT },
				},
			}}
		>
			{children}
		</motion.div>
	);
}
