import { useEffect, useMemo, useState } from "react";
import { AddTopicModal } from "./components/AddTopicModal";
import { AppLayout } from "./components/AppLayout";
import { dashboardApi, type ApiError } from "./lib/api";
import { DashboardScreen, type DashboardSource } from "./screens/DashboardScreen";
import type { Snapshot, Topic, TopicCreate } from "./types";

const validSources: DashboardSource[] = ["summary", "tiktok", "instagram", "facebook", "maps", "shopee", "youtube"];

function getSource(): DashboardSource {
  const source = window.location.hash.replace(/^#\/?/, "") || "summary";
  return validSources.includes(source as DashboardSource) ? source as DashboardSource : "summary";
}

export default function App() {
  const [source, setSource] = useState<DashboardSource>(getSource);
  const [topics, setTopics] = useState<Topic[]>([]);
  const [topicId, setTopicId] = useState("");
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isAddModalOpen, setIsAddModalOpen] = useState(false);
  const selectedTopic = useMemo(() => topics.find((topic) => topic.id === topicId), [topics, topicId]);

  useEffect(() => {
    const onHashChange = () => setSource(getSource());
    window.addEventListener("hashchange", onHashChange);
    dashboardApi.listTopics().then(({ topics: available }) => {
      setTopics(available);
      if (available[0]) setTopicId(available[0].id);
    }).catch((cause: Error) => setError(cause.message)).finally(() => setLoading(false));
    return () => window.removeEventListener("hashchange", onHashChange);
  }, []);

  useEffect(() => {
    if (!topicId) return;
    dashboardApi.getSnapshot(topicId).then(setSnapshot).catch((cause: Error) => setError(cause.message));
  }, [topicId]);

  useEffect(() => {
    if (!topicId) return;
    let timer: number | undefined;
    return dashboardApi.connectStream((event) => {
      if (event.topic_id && event.topic_id !== topicId) return;
      if (!["source_status", "evidence_new", "analysis_updated", "error"].includes(event.type)) return;
      window.clearTimeout(timer);
      timer = window.setTimeout(() => dashboardApi.getSnapshot(topicId).then(setSnapshot).catch((cause: Error) => setError(cause.message)), 250);
    }, () => undefined);
  }, [topicId]);

  async function refresh() {
    if (!topicId) return;
    setRefreshing(true);
    setError(null);
    try {
      await dashboardApi.refresh(topicId);
    } catch (cause) {
      const apiError = cause as ApiError;
      setError(apiError.message);
    } finally {
      setRefreshing(false);
    }
  }

  async function handleCreateTopic(payload: TopicCreate) {
    try {
      const topic = await dashboardApi.createTopic(payload);
      setTopics((current) => [...current, topic]);
      setTopicId(topic.id);
      setError(null);
    } catch (cause) {
      setError((cause as Error).message);
      throw cause;
    }
  }

  return (
    <>
      <AppLayout
        source={source}
        topic={selectedTopic}
        topics={topics}
        onSelectTopic={setTopicId}
        onAddTopic={() => setIsAddModalOpen(true)}
        onRefresh={refresh}
        refreshing={refreshing}
        error={error}
      >
        {loading ? (
          <main className="page-content">
            <div className="loading-state neo-box">Memuat snapshot tersimpan...</div>
          </main>
        ) : (
          <DashboardScreen
            snapshot={snapshot}
            source={source}
            onAddTopic={() => setIsAddModalOpen(true)}
          />
        )}
      </AppLayout>

      <AddTopicModal
        isOpen={isAddModalOpen}
        onClose={() => setIsAddModalOpen(false)}
        onSubmit={handleCreateTopic}
      />
    </>
  );
}
