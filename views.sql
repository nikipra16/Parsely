create or replace view bi_order_items as
select
  o.id as order_id,
  o.gmail_id,
  o.order_ts,
  (o.order_ts at time zone 'utc')::date as order_date_utc,
  o.store_name,
  o.category,
  o.from_email,
  o.total as order_total,
  oi.id as order_item_id,
  oi.brand,
  oi.item_name,
  oi.quantity,
  oi.item_price,
  (oi.quantity::numeric * oi.item_price) as item_total
from orders o
join order_items oi
  on oi.order_id = o.id;

create or replace view orders_daily as
select
  (o.order_ts at time zone 'utc')::date as order_date_utc,
  count(*) as orders_count,
  sum(o.total) as total_spend,
  avg(o.total) as avg_order_value
from orders o
group by 1;

create or replace view spend_by_store_monthly as
select
  date_trunc('month', o.order_ts at time zone 'utc')::date as month_utc,
  o.store_name,
  count(*) as orders_count,
  sum(o.total) as total_spend,
  avg(o.total) as avg_order_value
from orders o
group by 1, 2;

create or replace view top_items as
select
  oi.item_name,
  count(distinct oi.order_id) as times_bought,
  sum(oi.quantity) as total_quantity,
  sum(oi.quantity::numeric * oi.item_price) as total_spend,
  case
    when sum(oi.quantity) > 0 then (sum(oi.quantity::numeric * oi.item_price) / sum(oi.quantity))
    else null
  end as avg_unit_price,
  max(o.order_ts) as last_bought_ts
from order_items oi
join orders o on o.id = oi.order_id
group by 1;

