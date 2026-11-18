import Link from "next/link";

export default function NotFound() {
  return (
    <div className="py-20">
      <p className="eyebrow mb-2">404</p>
      <h1 className="text-2xl font-semibold">Page not found</h1>
      <p className="mt-2 text-sm text-ink-2">The page you requested does not exist.</p>
      <Link href="/" className="btn mt-6">Back to overview</Link>
    </div>
  );
}
