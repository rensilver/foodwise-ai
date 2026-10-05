import { MealWorkspace } from '../../../features/chat/meal-workspace';
export default async function Conversation({ params }: { params: Promise<{ id: string }> }) { return <MealWorkspace conversationId={(await params).id} />; }
