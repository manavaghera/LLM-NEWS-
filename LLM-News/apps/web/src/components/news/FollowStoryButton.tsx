import { Bell, BellRing } from 'lucide-react'
import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { library, useLibrary, type FollowedStory } from '@/lib/library'
import { api } from '@/api/client'

export function FollowStoryButton({ story }: { story: Omit<FollowedStory, 'followed_at'> }) {
  const data = useLibrary()
  const [error, setError] = useState('')
  const following = data.stories.some((s) => s.date === story.date && s.group_id === story.group_id
    && (!s.story_identity || !story.story_identity || s.story_identity === story.story_identity))
  const toggle = () => {
    try {
      library.toggleStory(story)
      if (!following) void api.analytics('story_followed').catch(() => undefined)
      setError('')
    } catch (failure) { setError(failure instanceof Error ? failure.message : 'Could not follow this story.') }
  }
  return <div className="space-y-1">
    <Button onClick={toggle} aria-pressed={following} title="Get in-app alerts for later coverage and changes to this article">
      {following ? <BellRing className="text-accent" /> : <Bell />} {following ? 'Following this story' : 'Follow this story'}
    </Button>
    {error && <p role="alert" className="max-w-xs text-xs text-negative">{error}</p>}
  </div>
}
