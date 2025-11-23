import { BrowserRouter as Router, Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import Dashboard from './pages/Dashboard'
import Portfolio from './pages/Portfolio'
import Holdings from './pages/Holdings'
import Backtest from './pages/Backtest'
import MLModel from './pages/MLModel'
import Lookback from './pages/Lookback'

function App() {
  return (
    <Router>
      <Layout>
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/portfolio" element={<Portfolio />} />
          <Route path="/holdings" element={<Holdings />} />
          <Route path="/backtest" element={<Backtest />} />
          <Route path="/ml-model" element={<MLModel />} />
          <Route path="/lookback" element={<Lookback />} />
        </Routes>
      </Layout>
    </Router>
  )
}

export default App
