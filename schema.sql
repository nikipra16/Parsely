
create table if not exists orders (
  id bigserial primary key,
  gmail_id text not null unique,
  order_ts timestamptz,
  store_name text,
  category text,
  from_email text,
  total numeric(12,2)
);

create index if not exists idx_orders_order_ts on orders(order_ts);
create index if not exists idx_orders_store on orders(store_name);
create index if not exists idx_orders_category on orders(category);

create table if not exists order_items (
  id bigserial primary key,
  order_id bigint not null references orders(id) on delete cascade,
  brand text,
  item_name text,
  quantity int,
  item_price numeric(12,2)
);

create table if not exists raw_gmail (
  gmail_id text primary key,
  date_ts timestamptz,
  subject text,
  from_email text,
  body text,
  html_body text
);

create table if not exists pipeline_run (
  id bigserial primary key,
  started_at timestamptz not null default now(),
  ended_at timestamptz,
  status text not null default 'running',
  start_date date,
  end_date date,
  limit_emails int,
  emails_fetched int default 0,
  emails_loaded int default 0,
  orders_upserted int default 0,
  orders_with_total int default 0,
  orders_missing_total int default 0,
  error text
);

-- Forward-compatible schema updates (safe to re-run)
alter table pipeline_run add column if not exists orders_upserted int default 0;
alter table pipeline_run add column if not exists orders_with_total int default 0;
alter table pipeline_run add column if not exists orders_missing_total int default 0;

create index if not exists idx_order_items_order_id on order_items(order_id);
create index if not exists idx_order_items_item_name on order_items(item_name);
create index if not exists idx_order_items_brands on order_items(brand);
create index if not exists idx_raw_from on raw_gmail(from_email);