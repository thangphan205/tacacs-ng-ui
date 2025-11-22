import { IconButton } from "@chakra-ui/react"
import { BsThreeDotsVertical } from "react-icons/bs"
import type { ProfileScriptPublic } from "@/client"
import DeleteProfileScript from "../ProfileScripts/DeleteProfileScript"
import EditProfileScript from "../ProfileScripts/EditProfileScript"
import { MenuContent, MenuRoot, MenuTrigger } from "../ui/menu"

interface ProfileScriptActionsMenuProps {
  profilescript: ProfileScriptPublic
}

export const ProfileScriptActionsMenu = ({ profilescript }: ProfileScriptActionsMenuProps) => {
  return (
    <MenuRoot>
      <MenuTrigger asChild>
        <IconButton variant="ghost" color="inherit">
          <BsThreeDotsVertical />
        </IconButton>
      </MenuTrigger>
      <MenuContent>
        <EditProfileScript profilescript={profilescript} />
        <DeleteProfileScript profilescript={profilescript} />
      </MenuContent>
    </MenuRoot>
  )
}
