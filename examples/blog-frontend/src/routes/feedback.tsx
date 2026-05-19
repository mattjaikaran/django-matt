import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Textarea } from '@/components/ui/textarea';
import { createFileRoute } from '@tanstack/react-router';
import { Bug, Lightbulb, MessageSquare, Star } from 'lucide-react';

export const Route = createFileRoute('/feedback')({
  component: FeedbackPage,
});

function FeedbackPage() {
  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    // TODO: wire to API
  };

  const feedbackTypes = [
    { value: 'bug', label: 'Bug Report', icon: Bug, color: 'text-red-500' },
    {
      value: 'feature',
      label: 'Feature Request',
      icon: Lightbulb,
      color: 'text-yellow-500',
    },
    {
      value: 'improvement',
      label: 'Improvement',
      icon: Star,
      color: 'text-blue-500',
    },
    {
      value: 'general',
      label: 'General Feedback',
      icon: MessageSquare,
      color: 'text-green-500',
    },
  ];

  return (
    <div className="page-container">
      <div className="mx-auto max-w-4xl space-y-8">
        <div className="space-y-4 text-center">
          <h1 className="text-4xl font-bold tracking-tight">Feedback</h1>
          <p className="text-xl text-muted-foreground">
            Help us improve by sharing your thoughts and suggestions
          </p>
        </div>

        <div className="grid gap-6 md:grid-cols-3">
          {feedbackTypes.map(type => (
            <Card key={type.value} className="text-center">
              <CardContent className="pt-6">
                <type.icon className={`mx-auto mb-3 h-8 w-8 ${type.color}`} />
                <h3 className="font-semibold">{type.label}</h3>
                <p className="mt-2 text-sm text-muted-foreground">
                  {type.value === 'bug' &&
                    "Report issues or bugs you've encountered"}
                  {type.value === 'feature' &&
                    'Suggest new features or functionality'}
                  {type.value === 'improvement' &&
                    'Ideas to make existing features better'}
                  {type.value === 'general' &&
                    'Share your overall experience and thoughts'}
                </p>
              </CardContent>
            </Card>
          ))}
        </div>

        <Card>
          <CardHeader>
            <CardTitle>Share Your Feedback</CardTitle>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleSubmit} className="space-y-6">
              <div className="grid gap-4 md:grid-cols-2">
                <div className="space-y-2">
                  <Label htmlFor="name">Name (Optional)</Label>
                  <Input id="name" placeholder="Your name" />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="email">Email (Optional)</Label>
                  <Input id="email" type="email" placeholder="your@email.com" />
                </div>
              </div>

              <div className="space-y-2">
                <Label htmlFor="type">Feedback Type</Label>
                <Select>
                  <SelectTrigger>
                    <SelectValue placeholder="Select feedback type" />
                  </SelectTrigger>
                  <SelectContent>
                    {feedbackTypes.map(type => (
                      <SelectItem key={type.value} value={type.value}>
                        <div className="flex items-center space-x-2">
                          <type.icon className={`h-4 w-4 ${type.color}`} />
                          <span>{type.label}</span>
                        </div>
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-2">
                <Label htmlFor="title">Title</Label>
                <Input
                  id="title"
                  placeholder="Brief summary of your feedback"
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="description">Description</Label>
                <Textarea
                  id="description"
                  placeholder="Provide detailed feedback, steps to reproduce (for bugs), or specific suggestions..."
                  className="min-h-[150px]"
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="priority">Priority</Label>
                <Select>
                  <SelectTrigger>
                    <SelectValue placeholder="Select priority level" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="low">Low - Nice to have</SelectItem>
                    <SelectItem value="medium">
                      Medium - Would be helpful
                    </SelectItem>
                    <SelectItem value="high">High - Important issue</SelectItem>
                    <SelectItem value="critical">
                      Critical - Blocking issue
                    </SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div className="flex gap-4">
                <Button type="submit" className="flex-1">
                  Submit Feedback
                </Button>
                <Button type="button" variant="outline">
                  Save Draft
                </Button>
              </div>
            </form>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Recent Feedback</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              <div className="flex items-start space-x-3 rounded-lg bg-muted/50 p-4">
                <Lightbulb className="mt-0.5 h-5 w-5 text-yellow-500" />
                <div className="flex-1">
                  <p className="font-medium">Add dark mode toggle to navbar</p>
                  <p className="mt-1 text-sm text-muted-foreground">
                    It would be great to have a quick way to switch between
                    light and dark modes.
                  </p>
                  <p className="mt-2 text-xs text-muted-foreground">
                    Feature Request • 2 days ago • ✅ Implemented
                  </p>
                </div>
              </div>

              <div className="flex items-start space-x-3 rounded-lg bg-muted/50 p-4">
                <Bug className="mt-0.5 h-5 w-5 text-red-500" />
                <div className="flex-1">
                  <p className="font-medium">
                    Form validation not working on mobile
                  </p>
                  <p className="mt-1 text-sm text-muted-foreground">
                    The form validation messages don't appear properly on mobile
                    devices.
                  </p>
                  <p className="mt-2 text-xs text-muted-foreground">
                    Bug Report • 1 week ago • 🔄 In Progress
                  </p>
                </div>
              </div>

              <div className="flex items-start space-x-3 rounded-lg bg-muted/50 p-4">
                <Star className="mt-0.5 h-5 w-5 text-blue-500" />
                <div className="flex-1">
                  <p className="font-medium">Improve loading states</p>
                  <p className="mt-1 text-sm text-muted-foreground">
                    Add skeleton loaders and better loading indicators
                    throughout the app.
                  </p>
                  <p className="mt-2 text-xs text-muted-foreground">
                    Improvement • 1 week ago • 📋 Planned
                  </p>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
