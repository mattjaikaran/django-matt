import { createFileRoute } from '@tanstack/react-router';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import api from '@/lib/api';
import { Mail, Send, Github, Linkedin } from 'lucide-react';
import { useState } from 'react';

export const Route = createFileRoute('/contact')({
  component: ContactPage,
});

const contactSchema = z.object({
  name: z.string().min(2, 'Name must be at least 2 characters'),
  email: z.string().email('Please enter a valid email address'),
  subject: z.string().optional(),
  message: z.string().min(10, 'Message must be at least 10 characters'),
});

type ContactFormValues = z.infer<typeof contactSchema>;

function ContactPage() {
  const [submitted, setSubmitted] = useState(false);

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
    reset,
  } = useForm<ContactFormValues>({
    resolver: zodResolver(contactSchema),
  });

  const onSubmit = async (values: ContactFormValues) => {
    try {
      await api.post('/contact', values);
      toast.success('Message sent! I\'ll get back to you soon.');
      setSubmitted(true);
      reset();
    } catch {
      toast.error('Failed to send message. Please try again or email me directly.');
    }
  };

  return (
    <div className="min-h-screen bg-slate-50">
      {/* Page header */}
      <div className="bg-white border-b">
        <div className="container mx-auto px-4 py-12">
          <div className="flex items-center gap-3 mb-2">
            <Mail className="h-7 w-7 text-indigo-500" />
            <h1 className="text-3xl font-bold">Contact</h1>
          </div>
          <p className="text-muted-foreground">
            Have a project in mind or want to chat? Drop me a message.
          </p>
        </div>
      </div>

      <div className="container mx-auto px-4 py-10">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-10 max-w-4xl mx-auto">
          {/* Contact info */}
          <div className="space-y-6">
            <div>
              <h2 className="text-lg font-semibold mb-2">Get in touch</h2>
              <p className="text-sm text-muted-foreground leading-relaxed">
                I'm always open to discussing new projects, opportunities, or just talking code.
              </p>
            </div>

            <div className="space-y-3">
              <a
                href="mailto:hello@example.dev"
                className="flex items-center gap-3 text-sm text-muted-foreground hover:text-foreground transition-colors"
              >
                <div className="h-8 w-8 rounded-full bg-indigo-50 flex items-center justify-center">
                  <Mail className="h-4 w-4 text-indigo-500" />
                </div>
                hello@example.dev
              </a>
              <a
                href="https://github.com/example"
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-3 text-sm text-muted-foreground hover:text-foreground transition-colors"
              >
                <div className="h-8 w-8 rounded-full bg-slate-100 flex items-center justify-center">
                  <Github className="h-4 w-4 text-slate-600" />
                </div>
                github.com/example
              </a>
              <a
                href="https://linkedin.com/in/example"
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-3 text-sm text-muted-foreground hover:text-foreground transition-colors"
              >
                <div className="h-8 w-8 rounded-full bg-blue-50 flex items-center justify-center">
                  <Linkedin className="h-4 w-4 text-blue-600" />
                </div>
                linkedin.com/in/example
              </a>
            </div>
          </div>

          {/* Form */}
          <div className="md:col-span-2">
            {submitted ? (
              <Card>
                <CardContent className="py-12 text-center">
                  <div className="h-12 w-12 rounded-full bg-green-100 flex items-center justify-center mx-auto mb-4">
                    <Send className="h-6 w-6 text-green-600" />
                  </div>
                  <h3 className="text-lg font-semibold mb-2">Message sent!</h3>
                  <p className="text-muted-foreground mb-4">
                    Thanks for reaching out. I'll get back to you as soon as possible.
                  </p>
                  <Button variant="outline" onClick={() => setSubmitted(false)}>
                    Send another message
                  </Button>
                </CardContent>
              </Card>
            ) : (
              <Card>
                <CardHeader>
                  <CardTitle>Send a message</CardTitle>
                  <CardDescription>
                    Fill in the form below and I'll respond within 1-2 business days.
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <form onSubmit={handleSubmit(onSubmit)} className="space-y-5">
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                      <div className="space-y-1.5">
                        <Label htmlFor="name">Name *</Label>
                        <Input
                          id="name"
                          placeholder="Your name"
                          {...register('name')}
                          aria-invalid={!!errors.name}
                        />
                        {errors.name && (
                          <p className="text-xs text-destructive">{errors.name.message}</p>
                        )}
                      </div>
                      <div className="space-y-1.5">
                        <Label htmlFor="email">Email *</Label>
                        <Input
                          id="email"
                          type="email"
                          placeholder="you@example.com"
                          {...register('email')}
                          aria-invalid={!!errors.email}
                        />
                        {errors.email && (
                          <p className="text-xs text-destructive">{errors.email.message}</p>
                        )}
                      </div>
                    </div>

                    <div className="space-y-1.5">
                      <Label htmlFor="subject">Subject</Label>
                      <Input
                        id="subject"
                        placeholder="What's this about? (optional)"
                        {...register('subject')}
                      />
                    </div>

                    <div className="space-y-1.5">
                      <Label htmlFor="message">Message *</Label>
                      <Textarea
                        id="message"
                        placeholder="Tell me about your project or question..."
                        rows={5}
                        {...register('message')}
                        aria-invalid={!!errors.message}
                      />
                      {errors.message && (
                        <p className="text-xs text-destructive">{errors.message.message}</p>
                      )}
                    </div>

                    <Button
                      type="submit"
                      className="w-full gap-2 bg-indigo-600 hover:bg-indigo-700"
                      disabled={isSubmitting}
                    >
                      <Send className="h-4 w-4" />
                      {isSubmitting ? 'Sending...' : 'Send Message'}
                    </Button>
                  </form>
                </CardContent>
              </Card>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
