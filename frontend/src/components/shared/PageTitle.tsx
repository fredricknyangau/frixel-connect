import { Helmet } from 'react-helmet-async';

interface PageTitleProps {
  title: string;
  description?: string;
}

export function PageTitle({ title, description }: PageTitleProps) {
  return (
    <Helmet>
      <title>{title} | Frixel Connect</title>
      {description && <meta name="description" content={description} />}
    </Helmet>
  );
}
