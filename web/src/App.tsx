import { useEffect, useState } from "react";
import { AppLayout } from "./components/AppLayout";
import { GoogleMapsScreen } from "./screens/GoogleMapsScreen";
import { HomeScreen } from "./screens/HomeScreen";
import { SnapshotScreen } from "./screens/SnapshotScreen";
import { SuaraPasarScreen } from "./screens/SuaraPasarScreen";
import { YouTubeScreen } from "./screens/YouTubeScreen";

export type ScreenPath = "/" | "/suara-pasar" | "/google-maps" | "/tren-youtube" | "/snapshot";

function getPath(): ScreenPath {
  const path = window.location.hash.replace(/^#/, "") || "/";
  return ["/", "/suara-pasar", "/google-maps", "/tren-youtube", "/snapshot"].includes(path)
    ? (path as ScreenPath)
    : "/";
}

export default function App() {
  const [path, setPath] = useState<ScreenPath>(getPath);

  useEffect(() => {
    const onHashChange = () => setPath(getPath());
    window.addEventListener("hashchange", onHashChange);
    return () => window.removeEventListener("hashchange", onHashChange);
  }, []);

  const screen = {
    "/": <HomeScreen />,
    "/suara-pasar": <SuaraPasarScreen />,
    "/google-maps": <GoogleMapsScreen />,
    "/tren-youtube": <YouTubeScreen />,
    "/snapshot": <SnapshotScreen />
  }[path];

  return <AppLayout path={path}>{screen}</AppLayout>;
}
