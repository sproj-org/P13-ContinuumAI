interface ContinuumIconProps {
  className?: string;
  size?: number;
}

export function ContinuumIcon({ className = "", size = 24 }: ContinuumIconProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
    >
      {/* Neural network nodes */}
      <circle cx="6" cy="6" r="1.5" fill="currentColor" />
      <circle cx="18" cy="6" r="1.5" fill="currentColor" />
      <circle cx="6" cy="18" r="1.5" fill="currentColor" />
      <circle cx="18" cy="18" r="1.5" fill="currentColor" />
      <circle cx="12" cy="12" r="2" fill="currentColor" />
      
      {/* Neural connections */}
      <path
        d="M7.5 6.5L10.5 11M13.5 11L16.5 6.5M7.5 17.5L10.5 13M13.5 13L16.5 17.5M6 7.5L6 16.5M18 7.5L18 16.5"
        stroke="currentColor"
        strokeWidth="1"
        strokeOpacity="0.6"
      />
      
      {/* Circuit elements */}
      <rect x="2" y="11" width="4" height="2" rx="1" fill="currentColor" fillOpacity="0.4" />
      <rect x="18" y="11" width="4" height="2" rx="1" fill="currentColor" fillOpacity="0.4" />
      <rect x="11" y="2" width="2" height="4" rx="1" fill="currentColor" fillOpacity="0.4" />
      <rect x="11" y="18" width="2" height="4" rx="1" fill="currentColor" fillOpacity="0.4" />
    </svg>
  );
}
