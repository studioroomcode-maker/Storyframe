-- ============================================================
-- StoryFrame Supabase Schema
-- Supabase 대시보드 > SQL Editor 에서 이 파일 전체를 실행하세요.
-- ============================================================

-- 1. 프로젝트 테이블 (스토리보드 저장)
create table if not exists public.projects (
  id            uuid primary key default gen_random_uuid(),
  user_id       uuid references auth.users on delete cascade not null,
  name          text not null default '새 프로젝트',
  video_name    text default '',
  video_duration float default 0,
  media_type    text default 'video',
  scene_count   int default 0,
  thumbnail     text,          -- base64 (첫 씬 썸네일, 압축)
  scenes_json   jsonb default '[]',     -- 씬 배열 (썸네일 포함)
  benchmark_json jsonb,                 -- 벤치마크 데이터
  created_at    timestamptz default now(),
  updated_at    timestamptz default now()
);

-- RLS: 본인 프로젝트만 접근
alter table public.projects enable row level security;

create policy "projects: own CRUD"
  on public.projects for all
  using (auth.uid() = user_id);

-- 2. 러닝 프로필 테이블 (AI 학습 DB 동기화)
create table if not exists public.learning_profiles (
  user_id    uuid references auth.users on delete cascade primary key,
  learning_db jsonb not null default '{"version":1,"entries":[]}',
  updated_at timestamptz default now()
);

alter table public.learning_profiles enable row level security;

create policy "learning_profiles: own CRUD"
  on public.learning_profiles for all
  using (auth.uid() = user_id);

-- 3. 공유 스토리보드 테이블
create table if not exists public.shared_storyboards (
  id           uuid primary key default gen_random_uuid(),
  project_id   uuid references public.projects on delete cascade not null,
  user_id      uuid references auth.users on delete cascade not null,
  share_token  text unique default encode(gen_random_bytes(16), 'hex'),
  is_active    boolean default true,
  view_count   int default 0,
  created_at   timestamptz default now()
);

alter table public.shared_storyboards enable row level security;

-- 소유자는 CRUD 가능
create policy "shared: own manage"
  on public.shared_storyboards for all
  using (auth.uid() = user_id);

-- 비로그인 포함 누구나 활성 공유 조회 가능
create policy "shared: public read"
  on public.shared_storyboards for select
  using (is_active = true);

-- projects 테이블도 shared_storyboards JOIN을 위해 anon 읽기 허용
-- (shared_storyboards를 통해 join하는 경우만)
create policy "projects: public read via share"
  on public.projects for select
  using (
    exists (
      select 1 from public.shared_storyboards s
      where s.project_id = projects.id and s.is_active = true
    )
  );

-- 4. 공유 조회수 자동 증가 함수 (선택사항)
create or replace function public.increment_share_view(token text)
returns void language sql security definer as $$
  update public.shared_storyboards
  set view_count = view_count + 1
  where share_token = token;
$$;
