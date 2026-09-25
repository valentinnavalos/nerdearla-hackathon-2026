import { zodResolver } from "@hookform/resolvers/zod"
import { useState } from "react"
import { useForm } from "react-hook-form"
import { toast } from "sonner"
import { z } from "zod"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form"
import { Input } from "@/components/ui/input"
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Textarea } from "@/components/ui/textarea"
import { createSession, uploadFile } from "@/lib/api"

const schema = z.object({
  title: z.string().min(1, "requerido"),
  speaker: z.string().optional(),
  source_lang: z.enum(["en", "es"]),
  sourceKind: z.enum(["mic", "file", "upload"]),
  file: z.string().optional(),
  loop: z.boolean(),
  glossary_text: z.string().optional(),
})

type FormValues = z.infer<typeof schema>

interface CreateRoomDialogProps {
  token: string
  onCreated: () => void
}

export function CreateRoomDialog({ token, onCreated }: CreateRoomDialogProps) {
  const [open, setOpen] = useState(false)
  const [uploadFileObj, setUploadFileObj] = useState<File | null>(null)
  const form = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: {
      title: "",
      speaker: "",
      source_lang: "en",
      sourceKind: "mic",
      file: "",
      loop: false,
      glossary_text: "",
    },
  })

  const sourceKind = form.watch("sourceKind")

  async function onSubmit(values: FormValues) {
    try {
      let file: string | null = null
      let source: "mic" | "file" = "mic"
      if (values.sourceKind === "mic") {
        source = "mic"
      } else if (values.sourceKind === "file") {
        source = "file"
        file = values.file?.trim() || null
      } else {
        if (!uploadFileObj) throw new Error("elegí un archivo")
        source = "file"
        const { file: uploaded } = await uploadFile(token, uploadFileObj)
        file = uploaded
      }
      await createSession(token, {
        title: values.title.trim(),
        speaker: values.speaker?.trim() ?? "",
        source_lang: values.source_lang,
        source,
        file,
        loop: values.loop,
        glossary_text: values.glossary_text || null,
      })
      form.reset()
      setUploadFileObj(null)
      setOpen(false)
      onCreated()
    } catch (err) {
      toast.error(`No se pudo crear la sala: ${err instanceof Error ? err.message : err}`)
    }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button type="button">Nueva sala</Button>
      </DialogTrigger>
      <DialogContent className="max-h-[85vh] overflow-y-auto sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Nueva sala</DialogTitle>
        </DialogHeader>
        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
            <FormField
              control={form.control}
              name="title"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Título</FormLabel>
                  <FormControl>
                    <Input {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="speaker"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Orador/a</FormLabel>
                  <FormControl>
                    <Input {...field} />
                  </FormControl>
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="source_lang"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Idioma de la charla</FormLabel>
                  <Select value={field.value} onValueChange={field.onChange}>
                    <FormControl>
                      <SelectTrigger className="w-full">
                        <SelectValue />
                      </SelectTrigger>
                    </FormControl>
                    <SelectContent>
                      <SelectItem value="en">English</SelectItem>
                      <SelectItem value="es">Español</SelectItem>
                    </SelectContent>
                  </Select>
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="sourceKind"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Fuente</FormLabel>
                  <FormControl>
                    <RadioGroup
                      value={field.value}
                      onValueChange={field.onChange}
                      className="flex gap-4"
                    >
                      <label className="flex items-center gap-2 text-sm">
                        <RadioGroupItem value="mic" /> Micrófono
                      </label>
                      <label className="flex items-center gap-2 text-sm">
                        <RadioGroupItem value="file" /> Archivo (samples/)
                      </label>
                      <label className="flex items-center gap-2 text-sm">
                        <RadioGroupItem value="upload" /> Subir mp3
                      </label>
                    </RadioGroup>
                  </FormControl>
                </FormItem>
              )}
            />
            {sourceKind === "file" && (
              <FormField
                control={form.control}
                name="file"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Archivo (ruta en samples/)</FormLabel>
                    <FormControl>
                      <Input placeholder="samples/en_talk_3min.mp3" {...field} />
                    </FormControl>
                  </FormItem>
                )}
              />
            )}
            {sourceKind === "upload" && (
              <FormItem>
                <FormLabel>Subir mp3</FormLabel>
                <FormControl>
                  <Input
                    type="file"
                    accept="audio/*"
                    onChange={(e) => setUploadFileObj(e.target.files?.[0] ?? null)}
                  />
                </FormControl>
              </FormItem>
            )}
            <FormField
              control={form.control}
              name="loop"
              render={({ field }) => (
                <FormItem className="flex flex-row items-center gap-2">
                  <FormControl>
                    <Checkbox checked={field.value} onCheckedChange={field.onChange} />
                  </FormControl>
                  <FormLabel className="font-normal">Repetir en loop</FormLabel>
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="glossary_text"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Glosario (un término por línea, "mal =&gt; bien" para reemplazos)</FormLabel>
                  <FormControl>
                    <Textarea
                      className="font-mono text-sm"
                      placeholder={'Kubernetes\ncubernetes => Kubernetes'}
                      {...field}
                    />
                  </FormControl>
                </FormItem>
              )}
            />
            <DialogFooter>
              <Button type="submit" disabled={form.formState.isSubmitting}>
                Crear sala
              </Button>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  )
}
