-- הפעלת טבלת משתמשים אנונימיים עם הפרדת אבטחה מלאה (Row Level Security)
create table if not exists public.user_profiles (
  device_id text primary key,
  device_secret text not null,
  telegram_chat_id text,
  daily_time text default '09:00',
  last_daily_sent text default '',
  payload jsonb not null default '{"products": [], "alerts": []}'::jsonb,
  updated_at timestamptz default now()
);

alter table public.user_profiles enable row level security;

-- מדיניות אבטחה (RLS): כל מכשיר מורשה לגשת אך ורק לשורה של עצמו באמצעות ה-device_id וה-device_secret האישיים שלו
create policy "Isolated device read own profile"
  on public.user_profiles for select
  using (
    device_id = current_setting('request.headers', true)::json->>'x-device-id'
    and device_secret = current_setting('request.headers', true)::json->>'x-device-secret'
  );

create policy "Isolated device insert own profile"
  on public.user_profiles for insert
  with check (
    device_id = current_setting('request.headers', true)::json->>'x-device-id'
    and device_secret = current_setting('request.headers', true)::json->>'x-device-secret'
  );

create policy "Isolated device update own profile"
  on public.user_profiles for update
  using (
    device_id = current_setting('request.headers', true)::json->>'x-device-id'
    and device_secret = current_setting('request.headers', true)::json->>'x-device-secret'
  );
