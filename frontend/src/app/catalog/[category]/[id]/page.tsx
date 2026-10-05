import { notFound } from 'next/navigation';
import { CatalogDetail } from '../../../../features/catalog/catalog-detail';
export default async function Detail({ params, searchParams }: { params: Promise<{ category: string; id: string }>; searchParams: Promise<{ returnTo?: string }> }) {
  const { category, id } = await params; if (!['restaurants','recipes'].includes(category)) notFound();
  return <CatalogDetail key={`${category}:${id}`} entity={{ category: category === 'recipes' ? 'recipe' : 'restaurant', id }} returnTo={(await searchParams).returnTo} />;
}
