import { useState } from 'react'
import { Sidebar } from './components/Sidebar'
import type { ConsoleTab } from './components/Sidebar'
import { SingleTurnView } from './components/SingleTurnView'
import { BatchOverviewView } from './components/BatchOverviewView'
import { FrameworkAlignView } from './components/FrameworkAlignView'
import styles from './App.module.css'

export default function App() {
  const [activeTab, setActiveTab] = useState<ConsoleTab>('single')

  return (
    <div className={styles.root}>
      <Sidebar activeTab={activeTab} onTabChange={setActiveTab} />

      <main className={styles.main}>
        <div className={styles.content}>
          {activeTab === 'single' && <SingleTurnView />}
          {activeTab === 'batch' && <BatchOverviewView />}
          {activeTab === 'framework' && <FrameworkAlignView />}
        </div>
      </main>
    </div>
  )
}
