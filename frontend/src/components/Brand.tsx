type BrandProps = {
    compact?: boolean;
};

export default function Brand({ compact = false }: BrandProps) {
    return (
        <div className={`flex items-center ${compact ? "gap-2" : "gap-3"}`}>
            <img
                src="/logo.png"
                alt="VEXUS Security"
                className={compact ? "h-9 w-9 object-contain" : "h-12 w-12 object-contain"}
            />
            <span className={`${compact ? "text-sm" : "text-base"} font-semibold tracking-[0.22em]`}>VEXUS</span>
        </div>
    );
}
