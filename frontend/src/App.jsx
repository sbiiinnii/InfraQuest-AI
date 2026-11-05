import Dashboard from './pages/Dashboard'
import Missions from './pages/Missions'
import Practice from './pages/Practice'
import { useRoute } from './lib/route'

export default function App() {
  const route = useRoute()
  if (route.page === 'missions') return <Missions />
  if (route.page === 'practice') return <Practice key={route.missionId} missionId={route.missionId} />
  return <Dashboard />
}
