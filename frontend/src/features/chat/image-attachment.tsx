"use client";
import { useEffect, useRef, useState } from 'react';
import Image from 'next/image';
import { Button } from '../../components/ui/button';
import { requireOk, type Schema } from '../../lib/api/client';
export function ImageAttachment({ onChange, disabled = false }: { onChange: (mediaId: string | undefined, blocked: boolean) => void; disabled?: boolean }) {
  const [preview, setPreview] = useState(''); const [status, setStatus] = useState(''); const [error, setError] = useState('');
  const active = useRef<AbortController | null>(null); const picker = useRef<HTMLInputElement>(null);
  useEffect(() => () => { if (preview) URL.revokeObjectURL(preview); }, [preview]);
  useEffect(() => () => active.current?.abort(), []);
  function remove() { active.current?.abort(); active.current = null; setPreview(''); setStatus(''); setError(''); onChange(undefined, false); if (picker.current) picker.current.value = ''; }
  async function select(file?: File) {
    if (!file) return;
    remove(); onChange(undefined, true);
    if (!['image/jpeg','image/png','image/webp'].includes(file.type) || file.size > 10 * 1024 * 1024) { setError('Choose a decoded JPEG, PNG or WebP of at most 10 MiB.'); return; }
    const abort = new AbortController(); active.current = abort;
    setPreview(URL.createObjectURL(file)); setStatus('Uploading image…');
    try {
      const form = new FormData(); form.set('file', file);
      const response = await requireOk(await fetch('/api/v1/media', { method: 'POST', body: form, credentials: 'same-origin', signal: abort.signal }));
      const receipt: Schema['MediaReceipt'] = await response.json();
      if (active.current !== abort || abort.signal.aborted) return;
      onChange(receipt.id, false); setStatus('Image ready.');
    } catch (e) { if (!abort.signal.aborted) { setStatus(''); setError(`${e instanceof Error ? e.message : 'Image upload failed.'} Select another image or remove this attachment.`); } }
  }
  return <section className="stack" aria-label="Image attachment"><label htmlFor="image-upload">Add image</label><input ref={picker} id="image-upload" type="file" accept="image/jpeg,image/png,image/webp" disabled={disabled} aria-describedby="image-guidance" onChange={(e) => { void select(e.target.files?.[0]); }} /><p className="note" id="image-guidance">JPEG, PNG or WebP, up to 10 MiB and 20 megapixels. The server checks and strips metadata. Images cannot establish allergen absence.</p>{preview && <Image unoptimized src={preview} width={360} height={240} alt="Your food image preview" style={{ maxWidth: '100%', height: 'auto' }} />}{status && <p role="status">{status}</p>}{error && <p className="notice error" role="alert">{error}</p>}{(preview || error) && <><Button type="button" variant="secondary" disabled={disabled} onClick={remove}>Remove image</Button><p className="note">Removal detaches the image from this draft; it does not delete stored media.</p></>}</section>;
}
